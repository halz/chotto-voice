"""Login dialog for Google OAuth authentication."""
from typing import Optional, Callable
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont

from ..api_client import ChottoVoiceAPI, UserSession


class LoginWorker(QThread):
    """Worker thread for OAuth login."""
    
    success = pyqtSignal(object)  # UserSession
    error = pyqtSignal(str)
    browser_opened = pyqtSignal()
    
    def __init__(self, api: ChottoVoiceAPI):
        super().__init__()
        self.api = api
    
    def run(self):
        try:
            session = self.api.login_with_google(
                on_browser_open=lambda: self.browser_opened.emit()
            )
            self.success.emit(session)
        except Exception as e:
            self.error.emit(str(e))


class LoginDialog(QDialog):
    """Login dialog with Google OAuth."""
    
    STYLE = """
        QDialog {
            background-color: #ffffff;
        }
        QLabel#title {
            font-size: 24px;
            font-weight: 600;
            color: #1a1a1a;
        }
        QLabel#subtitle {
            font-size: 14px;
            color: #666;
        }
        QLabel#status {
            font-size: 13px;
            color: #888;
        }
        QLabel#credits {
            font-size: 16px;
            font-weight: 500;
            color: #228be6;
        }
        QPushButton#google {
            background-color: #ffffff;
            color: #333;
            border: 1px solid #dadce0;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 14px;
            font-weight: 500;
            min-width: 200px;
        }
        QPushButton#google:hover {
            background-color: #f8f9fa;
            border-color: #bdc1c6;
        }
        QPushButton#google:disabled {
            background-color: #f1f3f4;
            color: #aaa;
        }
        QPushButton#skip {
            background: transparent;
            color: #666;
            border: none;
            font-size: 13px;
            padding: 8px;
        }
        QPushButton#skip:hover {
            color: #333;
        }
        QFrame#divider {
            background-color: #e9ecef;
        }
    """
    
    def __init__(
        self, 
        api: ChottoVoiceAPI,
        allow_offline: bool = True,
        parent=None
    ):
        super().__init__(parent)
        self.api = api
        self.allow_offline = allow_offline
        self.session: Optional[UserSession] = None
        self._worker: Optional[LoginWorker] = None
        
        self.setWindowTitle("Chotto Voice - ログイン")
        self.setFixedSize(400, 360)
        self.setModal(True)
        self.setStyleSheet(self.STYLE)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(40, 40, 40, 32)
        
        # Logo/Title
        title = QLabel("Chotto Voice")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("音声をテキストに、瞬時に。")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addSpacing(24)
        
        # Google login button
        self.google_btn = QPushButton("  Googleでログイン")
        self.google_btn.setObjectName("google")
        self.google_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.google_btn.clicked.connect(self._start_login)
        layout.addWidget(self.google_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Status
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.hide()
        layout.addWidget(self.status_label)
        
        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.setMaximumWidth(200)
        self.progress.hide()
        layout.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()
        
        # Divider
        if self.allow_offline:
            divider = QFrame()
            divider.setObjectName("divider")
            divider.setFixedHeight(1)
            layout.addWidget(divider)
            
            # Offline mode
            offline_row = QHBoxLayout()
            offline_label = QLabel("開発モードで続行")
            offline_label.setObjectName("status")
            offline_row.addWidget(offline_label)
            
            skip_btn = QPushButton("スキップ →")
            skip_btn.setObjectName("skip")
            skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            skip_btn.clicked.connect(self._skip_login)
            offline_row.addWidget(skip_btn)
            
            offline_row.addStretch()
            layout.addLayout(offline_row)
        
        # Credits info
        credits_label = QLabel("新規登録で100クレジット無料！")
        credits_label.setObjectName("credits")
        credits_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(credits_label)
    
    def _start_login(self):
        """Start Google OAuth login flow."""
        self.google_btn.setEnabled(False)
        self.status_label.setText("ブラウザでログイン中...")
        self.status_label.show()
        self.progress.show()
        
        self._worker = LoginWorker(self.api)
        self._worker.success.connect(self._on_login_success)
        self._worker.error.connect(self._on_login_error)
        self._worker.browser_opened.connect(self._on_browser_opened)
        self._worker.start()
    
    def _on_browser_opened(self):
        """Browser was opened for OAuth."""
        self.status_label.setText("ブラウザでGoogleアカウントを選択してください...")
    
    def _on_login_success(self, session: UserSession):
        """Handle successful login."""
        self.session = session
        self.progress.hide()
        self.status_label.setText(f"ログイン成功: {session.email}")
        
        if session.is_new_user:
            self.status_label.setText(f"ようこそ！ {session.credits}クレジットをプレゼント 🎉")
        
        # Close dialog after short delay
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, self.accept)
    
    def _on_login_error(self, error: str):
        """Handle login error."""
        self.google_btn.setEnabled(True)
        self.progress.hide()
        self.status_label.setText(f"❌ ログインエラー: {error}")
        self.status_label.setStyleSheet("color: #dc3545;")
    
    def _skip_login(self):
        """Skip login and use offline mode."""
        self.session = None
        self.reject()  # Reject means offline mode
    
    def get_session(self) -> Optional[UserSession]:
        """Get the logged in session, or None for offline mode."""
        return self.session


class AccountWidget(QFrame):
    """Widget showing account info and credits."""
    
    STYLE = """
        QFrame {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 12px;
        }
        QLabel#email {
            font-size: 13px;
            color: #495057;
        }
        QLabel#credits {
            font-size: 16px;
            font-weight: 600;
            color: #228be6;
        }
        QPushButton#buy {
            background-color: #228be6;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 500;
        }
        QPushButton#buy:hover {
            background-color: #1c7ed6;
        }
        QPushButton#logout {
            background: transparent;
            color: #868e96;
            border: none;
            font-size: 12px;
            padding: 4px;
        }
        QPushButton#logout:hover {
            color: #495057;
        }
    """
    
    credits_purchased = pyqtSignal()
    logout_requested = pyqtSignal()
    
    def __init__(self, api: ChottoVoiceAPI, parent=None):
        super().__init__(parent)
        self.api = api
        self.setStyleSheet(self.STYLE)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Email
        self.email_label = QLabel("")
        self.email_label.setObjectName("email")
        layout.addWidget(self.email_label)
        
        # Credits row
        credits_row = QHBoxLayout()
        credits_row.setSpacing(12)
        
        self.credits_label = QLabel("0 クレジット")
        self.credits_label.setObjectName("credits")
        credits_row.addWidget(self.credits_label)
        
        credits_row.addStretch()
        
        buy_btn = QPushButton("購入")
        buy_btn.setObjectName("buy")
        buy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        buy_btn.clicked.connect(self._on_buy_clicked)
        credits_row.addWidget(buy_btn)
        
        layout.addLayout(credits_row)
        
        # Logout
        logout_btn = QPushButton("ログアウト")
        logout_btn.setObjectName("logout")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.clicked.connect(lambda: self.logout_requested.emit())
        layout.addWidget(logout_btn, alignment=Qt.AlignmentFlag.AlignRight)
    
    def update_info(self):
        """Update account info from API."""
        if self.api.session:
            self.email_label.setText(self.api.session.email)
            self.credits_label.setText(f"{self.api.session.credits} クレジット")
    
    def _on_buy_clicked(self):
        """Open purchase dialog."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("クレジット購入")
        dialog.setFixedSize(300, 250)
        
        layout = QVBoxLayout(dialog)
        
        # Package list
        package_list = QListWidget()
        try:
            packages = self.api.get_packages()
            for pkg in packages:
                item = QListWidgetItem(f"{pkg['name']} - {pkg['credits']}クレジット (${pkg['price_cents']/100:.2f})")
                item.setData(Qt.ItemDataRole.UserRole, pkg['id'])
                package_list.addItem(item)
        except Exception as e:
            package_list.addItem(f"パッケージ取得エラー: {e}")
        
        layout.addWidget(package_list)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(lambda: self._purchase_package(
            package_list.currentItem().data(Qt.ItemDataRole.UserRole) if package_list.currentItem() else None,
            dialog
        ))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.exec()
    
    def _purchase_package(self, package_id: Optional[str], dialog: QDialog):
        """Purchase a credit package."""
        if not package_id:
            return
        
        try:
            self.api.purchase_credits(package_id)
            dialog.accept()
            # Will need to verify payment and refresh credits
            self.credits_purchased.emit()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "購入エラー", str(e))
