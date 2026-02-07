"""Billing API - Stripe integration for credit purchases."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
import stripe

from server.config import get_settings
from server.auth.jwt import get_current_user
from server.db import update_user_credits, add_credit_transaction, get_user_by_id
from server.db.models import User


router = APIRouter(prefix="/api/billing", tags=["billing"])


class CreditPackage(BaseModel):
    """Available credit package."""
    id: str
    name: str
    credits: int
    price_cents: int
    currency: str = "USD"


class CheckoutResponse(BaseModel):
    """Checkout session response."""
    checkout_url: str
    session_id: str


class CreditBalance(BaseModel):
    """Credit balance response."""
    credits: int
    user_id: str


# Available credit packages
CREDIT_PACKAGES = [
    CreditPackage(id="starter", name="Starter Pack", credits=500, price_cents=499),
    CreditPackage(id="pro", name="Pro Pack", credits=2000, price_cents=1499),
    CreditPackage(id="team", name="Team Pack", credits=10000, price_cents=4999),
]


def get_stripe():
    """Get configured Stripe client."""
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key
    return stripe


@router.get("/packages", response_model=list[CreditPackage])
async def list_packages():
    """List available credit packages."""
    return CREDIT_PACKAGES


@router.get("/balance", response_model=CreditBalance)
async def get_balance(current_user: User = Depends(get_current_user)):
    """Get current credit balance."""
    return CreditBalance(
        credits=current_user.credits,
        user_id=current_user.id,
    )


@router.post("/checkout/{package_id}", response_model=CheckoutResponse)
async def create_checkout_session(
    package_id: str,
    success_url: str = "chotto-voice://payment/success",
    cancel_url: str = "chotto-voice://payment/cancel",
    current_user: User = Depends(get_current_user)
):
    """Create a Stripe checkout session for credit purchase."""
    # Find package
    package = next((p for p in CREDIT_PACKAGES if p.id == package_id), None)
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    settings = get_settings()
    get_stripe()
    
    try:
        # Create checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": package.currency.lower(),
                    "product_data": {
                        "name": f"Chotto Voice - {package.name}",
                        "description": f"{package.credits} credits for voice transcription",
                    },
                    "unit_amount": package.price_cents,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            client_reference_id=current_user.id,
            metadata={
                "user_id": current_user.id,
                "package_id": package.id,
                "credits": str(package.credits),
            }
        )
        
        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id,
        )
        
    except stripe.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment error: {str(e)}"
        )


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    settings = get_settings()
    get_stripe()
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle checkout.session.completed
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        
        user_id = session.get("client_reference_id") or session["metadata"].get("user_id")
        credits = int(session["metadata"].get("credits", 0))
        package_id = session["metadata"].get("package_id")
        payment_id = session.get("payment_intent")
        
        if user_id and credits > 0:
            # Add credits to user
            await update_user_credits(user_id, credits)
            
            # Record transaction
            await add_credit_transaction(
                user_id=user_id,
                amount=credits,
                transaction_type="purchase",
                stripe_payment_id=payment_id,
                description=f"Purchased {package_id} package"
            )
    
    return {"status": "ok"}


@router.get("/verify/{session_id}")
async def verify_payment(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Verify a payment session and return updated credits."""
    get_stripe()
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status != "paid":
            return {
                "status": "pending",
                "payment_status": session.payment_status,
            }
        
        # Get updated user
        updated_user = await get_user_by_id(current_user.id)
        
        return {
            "status": "completed",
            "credits": updated_user.credits,
            "credits_added": int(session.metadata.get("credits", 0)),
        }
        
    except stripe.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not verify payment: {str(e)}"
        )
