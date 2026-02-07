"""Chotto Voice API Client - handles authentication and transcription via server."""
import webbrowser
import threading
import http.server
import socketserver
import urllib.parse
from typing import Optional, Callable
from dataclasses import dataclass

import httpx


@dataclass
class UserSession:
    """User session data."""
    access_token: str
    user_id: str
    email: str
    name: Optional[str]
    credits: int
    is_new_user: bool = False


class AuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler for OAuth callback."""
    
    auth_code: Optional[str] = None
    error: Optional[str] = None
    
    def do_GET(self):
        """Handle GET request from OAuth redirect."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if "code" in params:
            AuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h1>&#x2705; Login Successful!</h1>
                    <p>You can close this window and return to Chotto Voice.</p>
                    <script>window.close();</script>
                </body></html>
            """)
        elif "error" in params:
            AuthCallbackHandler.error = params.get("error_description", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"""
                <html><body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h1>&#x274C; Login Failed</h1>
                    <p>{AuthCallbackHandler.error}</p>
                </body></html>
            """.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress logging."""
        pass


class ChottoVoiceAPI:
    """API client for Chotto Voice server."""
    
    def __init__(
        self, 
        server_url: str = "https://api.chotto.voice",
        callback_port: int = 18080
    ):
        self.server_url = server_url.rstrip("/")
        self.callback_port = callback_port
        self.session: Optional[UserSession] = None
        self._client = httpx.Client(timeout=60.0)
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.session is not None
    
    @property
    def credits(self) -> int:
        """Get current credits."""
        return self.session.credits if self.session else 0
    
    def _headers(self) -> dict:
        """Get request headers with auth token."""
        headers = {"Content-Type": "application/json"}
        if self.session:
            headers["Authorization"] = f"Bearer {self.session.access_token}"
        return headers
    
    def login_with_google(self, on_browser_open: Optional[Callable] = None) -> UserSession:
        """Start Google OAuth flow.
        
        Opens browser for Google login, waits for callback, returns session.
        
        Args:
            on_browser_open: Optional callback when browser is opened
            
        Returns:
            UserSession on success
            
        Raises:
            Exception on auth failure
        """
        # Get auth URL from server
        response = self._client.get(f"{self.server_url}/auth/google/url")
        response.raise_for_status()
        data = response.json()
        
        # Update redirect URI to local callback
        auth_url = data["auth_url"].replace(
            "redirect_uri=",
            f"redirect_uri=http://localhost:{self.callback_port}/callback&"
        )
        
        # Reset handler state
        AuthCallbackHandler.auth_code = None
        AuthCallbackHandler.error = None
        
        # Start local server for callback
        server = socketserver.TCPServer(("", self.callback_port), AuthCallbackHandler)
        server.timeout = 300  # 5 minute timeout
        
        # Open browser
        if on_browser_open:
            on_browser_open()
        webbrowser.open(auth_url)
        
        # Wait for callback
        while AuthCallbackHandler.auth_code is None and AuthCallbackHandler.error is None:
            server.handle_request()
        
        server.server_close()
        
        if AuthCallbackHandler.error:
            raise Exception(f"Authentication failed: {AuthCallbackHandler.error}")
        
        # Exchange code for token
        response = self._client.post(
            f"{self.server_url}/auth/google/token",
            params={"code": AuthCallbackHandler.auth_code}
        )
        response.raise_for_status()
        data = response.json()
        
        self.session = UserSession(
            access_token=data["access_token"],
            user_id=data["user_id"],
            email=data["email"],
            name=data.get("name"),
            credits=data["credits"],
            is_new_user=data.get("is_new_user", False),
        )
        
        return self.session
    
    def login_with_token(self, access_token: str) -> UserSession:
        """Login with existing access token.
        
        Args:
            access_token: JWT access token
            
        Returns:
            UserSession on success
        """
        # Verify token by fetching user profile
        response = self._client.get(
            f"{self.server_url}/api/users/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        data = response.json()
        
        self.session = UserSession(
            access_token=access_token,
            user_id=data["id"],
            email=data["email"],
            name=data.get("name"),
            credits=data["credits"],
        )
        
        return self.session
    
    def logout(self):
        """Clear current session."""
        self.session = None
    
    def transcribe(
        self, 
        audio_data: bytes, 
        filename: str = "audio.wav",
        language: Optional[str] = None
    ) -> dict:
        """Transcribe audio using server API.
        
        Args:
            audio_data: Audio file bytes
            filename: Audio filename (for format detection)
            language: Optional language code
            
        Returns:
            dict with text, duration_seconds, credits_used, credits_remaining
        """
        if not self.is_authenticated:
            raise Exception("Not authenticated. Please login first.")
        
        files = {"audio": (filename, audio_data)}
        params = {}
        if language:
            params["language"] = language
        
        response = self._client.post(
            f"{self.server_url}/api/transcribe",
            headers={"Authorization": f"Bearer {self.session.access_token}"},
            files=files,
            params=params,
        )
        
        if response.status_code == 402:
            raise Exception("Insufficient credits. Please purchase more credits.")
        
        response.raise_for_status()
        data = response.json()
        
        # Update local credits
        self.session.credits = data["credits_remaining"]
        
        return data
    
    def get_credits(self) -> int:
        """Fetch current credit balance from server."""
        if not self.is_authenticated:
            return 0
        
        response = self._client.get(
            f"{self.server_url}/api/users/me/credits",
            headers=self._headers()
        )
        response.raise_for_status()
        data = response.json()
        
        self.session.credits = data["credits"]
        return data["credits"]
    
    def get_packages(self) -> list[dict]:
        """Get available credit packages."""
        response = self._client.get(f"{self.server_url}/api/billing/packages")
        response.raise_for_status()
        return response.json()
    
    def purchase_credits(self, package_id: str) -> str:
        """Start credit purchase flow.
        
        Args:
            package_id: ID of the package to purchase
            
        Returns:
            Checkout URL to open in browser
        """
        if not self.is_authenticated:
            raise Exception("Not authenticated. Please login first.")
        
        response = self._client.post(
            f"{self.server_url}/api/billing/checkout/{package_id}",
            headers=self._headers()
        )
        response.raise_for_status()
        data = response.json()
        
        # Open checkout in browser
        webbrowser.open(data["checkout_url"])
        
        return data["checkout_url"]
    
    def verify_payment(self, session_id: str) -> dict:
        """Verify payment and get updated credits.
        
        Args:
            session_id: Stripe checkout session ID
            
        Returns:
            dict with status and credits
        """
        if not self.is_authenticated:
            raise Exception("Not authenticated.")
        
        response = self._client.get(
            f"{self.server_url}/api/billing/verify/{session_id}",
            headers=self._headers()
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("credits"):
            self.session.credits = data["credits"]
        
        return data
