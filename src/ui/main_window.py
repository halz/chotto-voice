"""Main window for Chotto Voice."""
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QProgressBar,
    QSystemTrayIcon, QMenu, QComboBox, QGroupBox,
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QCheckBox, QMessageBox, QFrame, QListWidget, QListWidgetItem,
    QStackedWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QAction, QCloseEvent, QKeyEvent

import sys

from ..audio import AudioRecorder
from ..transcriber import Transcriber
from ..ai_client import AIClient
from ..hotkey import HotkeyManager, HotkeyConfig, HOTKEY_PRESETS
from ..audio_control import get_audio_controller, AudioController
from ..text_input import type_to_focused_field
from ..user_config import UserConfig, is_startup_enabled, set_startup_enabled
from .icon import create_tray_icon, create_recording_icon, create_processing_icon
from .overlay import OverlayIndicator


class HotkeyCapture(QLineEdit):
    """Line edit that captures key combinations."""
    
    hotkey_captured = pyqtSignal(str)
    
    # Style constants for visibility
    STYLE_NORMAL = """
        QLineEdit {
            background-color: #2d2d2d;
            color: #ffffff;
            border: 2px solid #555555;
            border-radius: 4px;
            padding: 6px;
            font-size: 14px;
        }
    """
    STYLE_CAPTURING = """
        QLineEdit {
            background-color: #3d3522;
            color: #ffffff;
            border: 2px solid #ffc107;
            border-radius: 4px;
            padding: 6px;
            font-size: 14px;
        }
    """
    STYLE_SUCCESS = """
        QLineEdit {
            background-color: #1e3d1e;
            color: #ffffff;
            border: 2px solid #28a745;
            border-radius: 4px;
            padding: 6px;
            font-size: 14px;
        }
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("クリックしてキーを押す...")
        self.setReadOnly(True)
        self._capturing = False
        self._modifiers = set()
        self.setStyleSheet(self.STYLE_NORMAL)
    
    def focusInEvent(self, event):
        """Start capturing when focused."""
        super().focusInEvent(event)
        self._capturing = True
        self._modifiers = set()
        self.setText("")
        self.setStyleSheet(self.STYLE_CAPTURING)
        self.setPlaceholderText("キーを押してください...")
    
    def focusOutEvent(self, event):
        """Stop capturing when focus lost."""
        super().focusOutEvent(event)
        self._capturing = False
        self.setStyleSheet(self.STYLE_NORMAL)
        if not self.text():
            self.setPlaceholderText("クリックしてキーを押す...")
    
    def keyPressEvent(self, event: QKeyEvent):
        """Capture key press."""
        if not self._capturing:
            return
        
        key = event.key()
        modifiers = event.modifiers()
        
        # Build key string
        parts = []
        
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("win")
        
        # Get the actual key
        key_name = self._get_key_name(key)
        if key_name and key_name not in ("ctrl", "shift", "alt", "win", "control", "meta"):
            parts.append(key_name)
            
            # Complete capture
            hotkey = "+".join(parts)
            self.setText(hotkey)
            self.hotkey_captured.emit(hotkey)
            self._capturing = False
            self.setStyleSheet(self.STYLE_SUCCESS)
            self.clearFocus()
    
    def _get_key_name(self, key: int) -> str:
        """Convert Qt key code to key name."""
        key_map = {
            Qt.Key.Key_Space: "space",
            Qt.Key.Key_Return: "enter",
            Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Escape: "esc",
            Qt.Key.Key_Backspace: "backspace",
            Qt.Key.Key_Delete: "delete",
            Qt.Key.Key_Insert: "insert",
            Qt.Key.Key_Home: "home",
            Qt.Key.Key_End: "end",
            Qt.Key.Key_PageUp: "pageup",
            Qt.Key.Key_PageDown: "pagedown",
            Qt.Key.Key_Up: "up",
            Qt.Key.Key_Down: "down",
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Right: "right",
            Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3",
            Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5", Qt.Key.Key_F6: "f6",
            Qt.Key.Key_F7: "f7", Qt.Key.Key_F8: "f8", Qt.Key.Key_F9: "f9",
            Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
            Qt.Key.Key_Control: "ctrl",
            Qt.Key.Key_Shift: "shift",
            Qt.Key.Key_Alt: "alt",
            Qt.Key.Key_Meta: "win",
            Qt.Key.Key_QuoteLeft: "`",
        }
        
        if key in key_map:
            return key_map[key]
        
        # Try to get character
        if 32 <= key <= 126:
            return chr(key).lower()
        
        return ""


class HotkeySettingsDialog(QDialog):
    """Dialog for configuring hotkey settings."""
    
    def __init__(self, current_hotkey: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ホットキー設定")
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        
        # Current hotkey display
        current_label = QLabel(f"現在のホットキー: {current_hotkey}")
        current_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(current_label)
        
        # Hotkey capture
        form = QFormLayout()
        
        self.hotkey_input = HotkeyCapture()
        self.hotkey_input.setText(current_hotkey)
        self.hotkey_input.hotkey_captured.connect(self._on_hotkey_captured)
        form.addRow("新しいホットキー:", self.hotkey_input)
        
        layout.addLayout(form)
        
        # Presets
        preset_group = QGroupBox("プリセット")
        preset_layout = QVBoxLayout(preset_group)
        
        # First row
        row1 = QHBoxLayout()
        for name, key in list(HOTKEY_PRESETS.items())[:3]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, k=key: self._set_preset(k))
            row1.addWidget(btn)
        preset_layout.addLayout(row1)
        
        # Second row
        row2 = QHBoxLayout()
        for name, key in list(HOTKEY_PRESETS.items())[3:]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, k=key: self._set_preset(k))
            row2.addWidget(btn)
        preset_layout.addLayout(row2)
        
        layout.addWidget(preset_group)
        
        # Instructions
        help_label = QLabel(
            "📌 使い方:\n"
            "• テキストボックスをクリック → キーを押して設定\n"
            "• ホールド: 押している間だけ録音\n"
            "• ダブルタップ: 録音開始 + スピーカーミュート"
        )
        help_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(help_label)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self._captured_hotkey = current_hotkey
    
    def _on_hotkey_captured(self, hotkey: str):
        """Handle captured hotkey."""
        self._captured_hotkey = hotkey
    
    def _set_preset(self, key: str):
        """Set a preset hotkey."""
        self.hotkey_input.setText(key)
        self._captured_hotkey = key
        self.hotkey_input.setStyleSheet(HotkeyCapture.STYLE_SUCCESS)
    
    def get_hotkey(self) -> str:
        return self._captured_hotkey or self.hotkey_input.text()


class FirstRunSetupDialog(QDialog):
    """First-run setup dialog for API key configuration."""
    
    STYLE = """
        QDialog {
            background-color: #fafafa;
        }
        QLabel {
            color: #333;
        }
        QLabel#title {
            font-size: 20px;
            font-weight: 600;
            color: #1a1a1a;
        }
        QLabel#subtitle {
            font-size: 13px;
            color: #666;
        }
        QLabel#section {
            font-size: 14px;
            font-weight: 600;
            color: #1a1a1a;
            padding-top: 8px;
        }
        QLabel#hint {
            font-size: 12px;
            color: #888;
        }
        QLineEdit {
            padding: 10px 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background: white;
            font-size: 13px;
        }
        QLineEdit:focus {
            border-color: #4A90D9;
        }
        QPushButton#link {
            background: transparent;
            color: #4A90D9;
            border: none;
            font-size: 13px;
            padding: 0;
        }
        QPushButton#link:hover {
            color: #357ABD;
            text-decoration: underline;
        }
        QPushButton#primary {
            background-color: #2563eb;
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: 12px 32px;
            font-size: 14px;
            font-weight: 600;
            min-width: 100px;
        }
        QPushButton#primary:hover {
            background-color: #1d4ed8;
        }
        QPushButton#secondary {
            background-color: #f3f4f6;
            color: #374151;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 14px;
            min-width: 80px;
        }
        QPushButton#secondary:hover {
            background-color: #e5e7eb;
        }
    """
    
    def __init__(self, user_config: 'UserConfig', parent=None):
        super().__init__(parent)
        self.user_config = user_config
        self.setWindowTitle("Chotto Voice")
        self.setFixedSize(440, 480)
        self.setModal(True)
        self.setStyleSheet(self.STYLE)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(32, 32, 32, 24)
        
        # Title
        title = QLabel("Chotto Voice")
        title.setObjectName("title")
        layout.addWidget(title)
        
        subtitle = QLabel("音声入力を始めましょう")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        
        layout.addSpacing(16)
        
        # Gemini (Free - Primary)
        gemini_section = QLabel("Google Gemini（無料）")
        gemini_section.setObjectName("section")
        layout.addWidget(gemini_section)
        
        self.gemini_key_input = QLineEdit()
        self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_input.setPlaceholderText("APIキーを入力")
        layout.addWidget(self.gemini_key_input)
        
        gemini_hint_layout = QHBoxLayout()
        gemini_hint = QLabel("AI整形に使用")
        gemini_hint.setObjectName("hint")
        gemini_hint_layout.addWidget(gemini_hint)
        gemini_hint_layout.addStretch()
        gemini_link = QPushButton("キーを取得 →")
        gemini_link.setObjectName("link")
        gemini_link.setCursor(Qt.CursorShape.PointingHandCursor)
        gemini_link.clicked.connect(lambda: self._open_url("https://aistudio.google.com/app/apikey"))
        gemini_hint_layout.addWidget(gemini_link)
        layout.addLayout(gemini_hint_layout)
        
        layout.addSpacing(8)
        
        # OpenAI (Optional)
        openai_section = QLabel("OpenAI（オプション）")
        openai_section.setObjectName("section")
        layout.addWidget(openai_section)
        
        self.openai_key_input = QLineEdit()
        self.openai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_input.setPlaceholderText("sk-...")
        layout.addWidget(self.openai_key_input)
        
        openai_hint_layout = QHBoxLayout()
        openai_hint = QLabel("高精度な文字起こしに使用")
        openai_hint.setObjectName("hint")
        openai_hint_layout.addWidget(openai_hint)
        openai_hint_layout.addStretch()
        openai_link = QPushButton("キーを取得 →")
        openai_link.setObjectName("link")
        openai_link.setCursor(Qt.CursorShape.PointingHandCursor)
        openai_link.clicked.connect(lambda: self._open_url("https://platform.openai.com/api-keys"))
        openai_hint_layout.addWidget(openai_link)
        layout.addLayout(openai_hint_layout)
        
        layout.addSpacing(8)
        
        # Anthropic (Optional)
        anthropic_section = QLabel("Anthropic（オプション）")
        anthropic_section.setObjectName("section")
        layout.addWidget(anthropic_section)
        
        self.anthropic_key_input = QLineEdit()
        self.anthropic_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key_input.setPlaceholderText("sk-ant-...")
        layout.addWidget(self.anthropic_key_input)
        
        anthropic_hint_layout = QHBoxLayout()
        anthropic_hint = QLabel("Claude AIを使用する場合")
        anthropic_hint.setObjectName("hint")
        anthropic_hint_layout.addWidget(anthropic_hint)
        anthropic_hint_layout.addStretch()
        anthropic_link = QPushButton("キーを取得 →")
        anthropic_link.setObjectName("link")
        anthropic_link.setCursor(Qt.CursorShape.PointingHandCursor)
        anthropic_link.clicked.connect(lambda: self._open_url("https://console.anthropic.com/settings/keys"))
        anthropic_hint_layout.addWidget(anthropic_link)
        layout.addLayout(anthropic_hint_layout)
        
        # Spacer
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        skip_btn = QPushButton("スキップ")
        skip_btn.setObjectName("secondary")
        skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_btn.clicked.connect(self.reject)
        button_layout.addWidget(skip_btn)
        
        button_layout.addStretch()
        
        save_btn = QPushButton("開始する")
        save_btn.setObjectName("primary")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_and_accept)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def _open_url(self, url: str):
        """Open URL in browser."""
        import webbrowser
        webbrowser.open(url)
    
    def _save_and_accept(self):
        """Save API keys and accept dialog."""
        gemini_key = self.gemini_key_input.text().strip()
        openai_key = self.openai_key_input.text().strip()
        anthropic_key = self.anthropic_key_input.text().strip()
        
        # Save to config
        self.user_config.update(
            gemini_api_key=gemini_key,
            openai_api_key=openai_key,
            anthropic_api_key=anthropic_key,
            # If OpenAI key provided, use API for transcription
            whisper_provider="api" if openai_key else "local"
        )
        
        self.accept()
    
    def get_keys(self) -> dict:
        """Return the entered API keys."""
        return {
            "gemini": self.gemini_key_input.text().strip(),
            "openai": self.openai_key_input.text().strip(),
            "anthropic": self.anthropic_key_input.text().strip()
        }


class TranscriptionWorker(QThread):
    """Worker thread for transcription + AI processing."""
    
    transcription_done = pyqtSignal(str)  # Raw transcription
    ai_chunk = pyqtSignal(str)  # Streaming AI response
    finished = pyqtSignal(str)  # Final result
    error = pyqtSignal(str)
    
    def __init__(
        self, 
        transcriber: Transcriber, 
        ai_client: Optional[AIClient],
        audio_data: bytes,
        process_with_ai: bool = True
    ):
        super().__init__()
        self.transcriber = transcriber
        self.ai_client = ai_client
        self.audio_data = audio_data
        self.process_with_ai = process_with_ai
    
    def run(self):
        try:
            # Check for silence first
            from ..audio import AudioRecorder
            if not AudioRecorder.check_audio_has_speech(self.audio_data):
                print("[Worker] Audio too quiet (silence detected), skipping", flush=True)
                self.finished.emit("")
                return
            
            # Step 1: Transcribe
            print(f"[Worker] Transcribing audio ({len(self.audio_data)} bytes)...", flush=True)
            text = self.transcriber.transcribe(self.audio_data)
            print(f"[Worker] Transcription: '{text[:50] if text else '(empty)'}...'", flush=True)
            self.transcription_done.emit(text)
            
            if not text:
                print("[Worker] No text, skipping AI", flush=True)
                self.finished.emit("")
                return
            
            # Step 2: AI processing (if enabled and available)
            print(f"[Worker] AI: process_with_ai={self.process_with_ai}, client={self.ai_client is not None}", flush=True)
            if self.process_with_ai and self.ai_client:
                print(f"[Worker] Starting AI processing with {type(self.ai_client).__name__}...", flush=True)
                result_text = ""
                for chunk in self.ai_client.process_stream(text):
                    print(f"[Worker] AI chunk: '{chunk}'", flush=True)
                    self.ai_chunk.emit(chunk)
                    result_text += chunk
                print(f"[Worker] AI result: '{result_text[:50] if result_text else '(empty)'}...'", flush=True)
                self.finished.emit(result_text)
            else:
                print("[Worker] Skipping AI, using raw text", flush=True)
                self.finished.emit(text)
                
        except Exception as e:
            print(f"[Worker] Error: {e}", flush=True)
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""
    
    STYLE = """
        QMainWindow {
            background-color: #ffffff;
        }
        QWidget#sidebar {
            background-color: #f8f9fa;
            border-right: 1px solid #e9ecef;
        }
        QWidget#content {
            background-color: #ffffff;
        }
        QListWidget {
            background-color: transparent;
            border: none;
            font-size: 13px;
            outline: none;
        }
        QListWidget::item {
            padding: 12px 16px;
            border-radius: 6px;
            margin: 2px 8px;
            color: #495057;
        }
        QListWidget::item:selected {
            background-color: #e7f1ff;
            color: #1971c2;
        }
        QListWidget::item:hover:!selected {
            background-color: #f1f3f4;
        }
        QLabel#appTitle {
            font-size: 16px;
            font-weight: 600;
            color: #212529;
            padding: 16px;
        }
        QLabel#pageTitle {
            font-size: 18px;
            font-weight: 600;
            color: #212529;
            padding-bottom: 8px;
        }
        QLabel#sectionTitle {
            font-size: 13px;
            font-weight: 600;
            color: #495057;
            padding-top: 16px;
            padding-bottom: 4px;
        }
        QLabel#hint {
            font-size: 12px;
            color: #868e96;
        }
        QLabel#settingLabel {
            font-size: 13px;
            color: #212529;
        }
        QLineEdit {
            padding: 8px 12px;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            background: #ffffff;
            font-size: 13px;
            min-height: 18px;
            color: #212529;
        }
        QLineEdit:focus {
            border-color: #74c0fc;
            outline: none;
        }
        QComboBox {
            padding: 8px 12px;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            background: #ffffff;
            font-size: 13px;
            min-height: 18px;
            color: #212529;
        }
        QComboBox:focus {
            border-color: #74c0fc;
        }
        QComboBox::drop-down {
            border: none;
            width: 30px;
            subcontrol-position: right center;
            subcontrol-origin: padding;
        }
        QComboBox::down-arrow {
            width: 0;
            height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #868e96;
        }
        QComboBox:disabled {
            background: #f1f3f5;
            color: #adb5bd;
        }
        QWidget#posGrid {
            background: #e9ecef;
            border-radius: 8px;
        }
        QPushButton#posBtn {
            border: 1px solid #ced4da;
            border-radius: 4px;
            background: #ffffff;
            font-size: 14px;
            color: #adb5bd;
            padding: 4px;
        }
        QPushButton#posBtn:hover {
            background: #f8f9fa;
            border-color: #adb5bd;
            color: #495057;
        }
        QPushButton#posBtn:checked {
            background: #228be6;
            border-color: #1971c2;
            color: white;
        }
        QLineEdit#hotkeyInput {
            padding: 10px 14px;
            border: 2px solid #dee2e6;
            border-radius: 8px;
            background: #ffffff;
            font-size: 14px;
            font-weight: 500;
            color: #212529;
        }
        QLineEdit#hotkeyInput:focus {
            border-color: #228be6;
            background: #f8f9fa;
        }
        QComboBox QAbstractItemView {
            background-color: white;
            border: 1px solid #dee2e6;
            selection-background-color: #e7f1ff;
            selection-color: #212529;
            color: #212529;
            outline: none;
            padding: 4px;
        }
        QComboBox QAbstractItemView::item {
            padding: 6px 12px;
            min-height: 24px;
            color: #212529;
            background-color: white;
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: #e7f1ff;
            color: #212529;
        }
        QTextEdit {
            border: 1px solid #dee2e6;
            border-radius: 6px;
            background: #ffffff;
            font-size: 13px;
            padding: 8px;
        }
        QCheckBox {
            font-size: 13px;
            color: #212529;
            spacing: 10px;
            padding: 4px 0;
        }
        QCheckBox::indicator {
            width: 40px;
            height: 22px;
            border-radius: 11px;
            border: none;
            background: #ced4da;
        }
        QCheckBox::indicator:checked {
            background: #228be6;
        }
        QPushButton#primary {
            background-color: #228be6;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-size: 13px;
            font-weight: 500;
        }
        QPushButton#primary:hover {
            background-color: #1c7ed6;
        }
        QPushButton#secondary {
            background-color: #f8f9fa;
            color: #495057;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
        }
        QPushButton#secondary:hover {
            background-color: #e9ecef;
        }
        QProgressBar {
            border: none;
            background: #e9ecef;
            border-radius: 2px;
            max-height: 4px;
        }
        QProgressBar::chunk {
            background: #228be6;
            border-radius: 2px;
        }
    """
    
    # Signals for thread-safe UI updates
    _start_recording_signal = pyqtSignal()
    _stop_recording_signal = pyqtSignal()
    _mute_changed_signal = pyqtSignal(bool)
    
    def __init__(
        self,
        recorder: AudioRecorder,
        transcriber: Transcriber,
        ai_client: Optional[AIClient] = None,
        hotkey_config: Optional[HotkeyConfig] = None,
        user_config: Optional[UserConfig] = None
    ):
        super().__init__()
        self.recorder = recorder
        self.transcriber = transcriber
        self.ai_client = ai_client
        
        self._worker: Optional[TranscriptionWorker] = None
        
        # Audio controller for muting
        self.audio_controller: AudioController = get_audio_controller()
        self._was_muted_before_recording = False
        
        # User config (persistent settings)
        self.user_config = user_config or UserConfig.load()
        
        # Settings from user config
        self._auto_type = self.user_config.auto_type
        self._process_with_ai = self.user_config.process_with_ai
        
        # Setup hotkey manager with config from user_config
        self.hotkey_config = hotkey_config or HotkeyConfig(
            key=self.user_config.hotkey,
            double_tap_threshold=self.user_config.hotkey_double_tap_threshold,
            hold_threshold=self.user_config.hotkey_hold_threshold
        )
        self.hotkey_manager = HotkeyManager(
            config=self.hotkey_config,
            on_record_start=self._on_hotkey_record_start,
            on_record_stop=self._on_hotkey_record_stop,
            on_mute_toggle=self._on_hotkey_mute_toggle
        )
        
        # Connect signals for thread-safe UI updates
        self._start_recording_signal.connect(self._start_recording)
        self._stop_recording_signal.connect(self._stop_recording)
        self._mute_changed_signal.connect(self._update_mute_status)
        
        self._setup_ui()
        self._setup_tray()
        self._setup_overlay()
        
        # Start hotkey listening
        self.hotkey_manager.start()
        
        # Show warning if transcriber is not available
        if self.transcriber is None:
            self.status_label.setText("⚠️ 音声認識が利用不可（OpenAI APIキーを確認）")
            self.status_label.setStyleSheet("color: orange;")
            self.record_btn.setEnabled(False)
    
    def _setup_ui(self):
        """Setup the user interface with sidebar navigation."""
        self.setWindowTitle("Chotto Voice")
        self.setFixedSize(580, 520)
        self.setStyleSheet(self.STYLE)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )
        
        # Central widget with horizontal layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === Sidebar ===
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(160)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        # App title in sidebar
        app_title = QLabel("Chotto Voice")
        app_title.setObjectName("appTitle")
        sidebar_layout.addWidget(app_title)
        
        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.addItem("設定")
        self.nav_list.addItem("音声認識")
        self.nav_list.addItem("APIキー")
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        sidebar_layout.addWidget(self.nav_list)
        
        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)
        
        # === Content Area ===
        content = QWidget()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(0)
        
        # Stacked widget for pages
        self.page_stack = QStackedWidget()
        content_layout.addWidget(self.page_stack)
        
        # Create pages
        self._create_settings_page()
        self._create_whisper_page()
        self._create_api_page()
        
        main_layout.addWidget(content)
        
        # Hidden elements for compatibility
        self.mute_indicator = QLabel("🔊")
        self.level_bar = QProgressBar()
        self.level_bar.setMaximum(100)
        self.result_text = QTextEdit()
        self.record_btn = QPushButton()  # Hidden, for hotkey
    
    def _create_settings_page(self):
        """Create the general settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Page title
        title = QLabel("設定")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        
        # Status
        self.status_label = QLabel("準備完了")
        self.status_label.setObjectName("hint")
        layout.addWidget(self.status_label)
        
        layout.addSpacing(8)
        
        # Options
        self.auto_type_check = QCheckBox("フォーカス中のフィールドに入力")
        self.auto_type_check.setChecked(self._auto_type)
        self.auto_type_check.toggled.connect(self._on_auto_type_changed)
        layout.addWidget(self.auto_type_check)
        
        self.ai_process_check = QCheckBox("AIで文章を整形")
        self.ai_process_check.setChecked(self._process_with_ai)
        self.ai_process_check.setEnabled(self.ai_client is not None)
        self.ai_process_check.toggled.connect(self._on_ai_process_changed)
        layout.addWidget(self.ai_process_check)
        
        if sys.platform == "win32":
            self.startup_check = QCheckBox("Windowsと一緒に起動")
            self.startup_check.setChecked(is_startup_enabled())
            self.startup_check.toggled.connect(self._on_startup_changed)
            layout.addWidget(self.startup_check)
        
        layout.addSpacing(12)
        
        # Overlay position (visual grid)
        overlay_label = QLabel("インジケーター位置")
        overlay_label.setObjectName("sectionTitle")
        layout.addWidget(overlay_label)
        
        # Create position grid (compact)
        from PyQt6.QtWidgets import QGridLayout, QButtonGroup
        pos_container = QWidget()
        pos_container.setObjectName("posGrid")
        pos_container.setFixedSize(156, 70)
        pos_grid = QGridLayout(pos_container)
        pos_grid.setSpacing(4)
        pos_grid.setContentsMargins(6, 6, 6, 6)
        
        self.pos_buttons = {}
        self.pos_button_group = QButtonGroup(self)
        positions = [
            ("top-left", 0, 0), 
            ("top-center", 0, 1), 
            ("top-right", 0, 2),
            ("bottom-left", 1, 0), 
            ("bottom-center", 1, 1), 
            ("bottom-right", 1, 2)
        ]
        
        current_pos = self.user_config.overlay_position
        for pos_key, row, col in positions:
            btn = QPushButton("🎤")
            btn.setObjectName("posBtn")
            btn.setCheckable(True)
            btn.setFixedSize(46, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if pos_key == current_pos:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, k=pos_key: self._on_position_btn_clicked(k))
            self.pos_buttons[pos_key] = btn
            self.pos_button_group.addButton(btn)
            pos_grid.addWidget(btn, row, col)
        
        layout.addWidget(pos_container)
        
        # Keep combo hidden for compatibility
        self.overlay_position_combo = QComboBox()
        self.overlay_position_combo.hide()
        self.pos_status_label = QLabel()  # Hidden, for compatibility
        
        layout.addSpacing(16)
        
        # Hotkey
        hotkey_label = QLabel("ホットキー")
        hotkey_label.setObjectName("sectionTitle")
        layout.addWidget(hotkey_label)
        
        hotkey_hint = QLabel("キーを押して設定（ダブルタップで録音開始）")
        hotkey_hint.setObjectName("hint")
        layout.addWidget(hotkey_hint)
        
        # Hotkey capture field (inline)
        self.hotkey_input = HotkeyCapture()
        self.hotkey_input.setObjectName("hotkeyInput")
        self.hotkey_input.setText(self.hotkey_config.key)
        self.hotkey_input.setFixedWidth(200)
        self.hotkey_input.setPlaceholderText("クリックしてキーを押す")
        self.hotkey_input.hotkey_captured.connect(self._on_inline_hotkey_captured)
        layout.addWidget(self.hotkey_input)
        
        # Hotkey presets
        preset_label = QLabel("プリセット")
        preset_label.setObjectName("hint")
        layout.addWidget(preset_label)
        
        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        for name, key in [("右Ctrl", "right ctrl"), ("右Shift", "right shift"), ("右Alt", "right alt"), ("F9", "f9")]:
            btn = QPushButton(name)
            btn.setObjectName("secondary")
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._set_hotkey_preset(k))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        layout.addLayout(preset_row)
        
        # Keep reference for compatibility
        self.hotkey_label = self.hotkey_input
        self.hotkey_btn = QPushButton()
        self.hotkey_btn.hide()
        
        layout.addStretch()
        self.page_stack.addWidget(page)
    
    def _create_whisper_page(self):
        """Create the Whisper/speech recognition page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Page title
        title = QLabel("音声認識")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        
        hint = QLabel("Whisperによる音声認識の設定")
        hint.setObjectName("hint")
        layout.addWidget(hint)
        
        layout.addSpacing(16)
        
        # Provider
        provider_label = QLabel("認識エンジン")
        provider_label.setObjectName("sectionTitle")
        layout.addWidget(provider_label)
        
        self.whisper_provider_combo = QComboBox()
        self.whisper_provider_combo.addItem("ローカル（無料・オフライン）", "local")
        self.whisper_provider_combo.addItem("OpenAI API（高速・高精度）", "api")
        self.whisper_provider_combo.setFixedWidth(250)
        current_provider = self.user_config.whisper_provider
        self.whisper_provider_combo.setCurrentIndex(0 if current_provider == "local" else 1)
        self.whisper_provider_combo.currentIndexChanged.connect(self._on_whisper_provider_changed)
        layout.addWidget(self.whisper_provider_combo)
        
        layout.addSpacing(16)
        
        # Model
        model_label = QLabel("モデルサイズ")
        model_label.setObjectName("sectionTitle")
        layout.addWidget(model_label)
        
        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.addItem("tiny（最速・39MB）", "tiny")
        self.whisper_model_combo.addItem("base（バランス・74MB）", "base")
        self.whisper_model_combo.addItem("small（高精度・244MB）", "small")
        self.whisper_model_combo.setFixedWidth(250)
        model_map = {"tiny": 0, "base": 1, "small": 2}
        self.whisper_model_combo.setCurrentIndex(model_map.get(self.user_config.whisper_local_model, 2))
        self.whisper_model_combo.setEnabled(current_provider == "local")
        self.whisper_model_combo.currentIndexChanged.connect(self._on_whisper_model_changed)
        layout.addWidget(self.whisper_model_combo)
        
        model_hint = QLabel("ローカルモード時のみ選択可能")
        model_hint.setObjectName("hint")
        layout.addWidget(model_hint)
        
        layout.addStretch()
        self.page_stack.addWidget(page)
    
    def _create_api_page(self):
        """Create the API keys page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Page title
        title = QLabel("APIキー")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        
        hint = QLabel("各サービスのAPIキーを設定")
        hint.setObjectName("hint")
        layout.addWidget(hint)
        
        layout.addSpacing(16)
        
        # Gemini
        gemini_label = QLabel("Google Gemini（無料）")
        gemini_label.setObjectName("sectionTitle")
        layout.addWidget(gemini_label)
        
        self.gemini_key_input = QLineEdit()
        self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_input.setPlaceholderText("AIza...")
        if self.user_config.gemini_api_key:
            self.gemini_key_input.setText(self.user_config.gemini_api_key)
        layout.addWidget(self.gemini_key_input)
        
        # OpenAI
        openai_label = QLabel("OpenAI")
        openai_label.setObjectName("sectionTitle")
        layout.addWidget(openai_label)
        
        self.openai_key_input = QLineEdit()
        self.openai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_input.setPlaceholderText("sk-...")
        if self.user_config.openai_api_key:
            self.openai_key_input.setText(self.user_config.openai_api_key)
        layout.addWidget(self.openai_key_input)
        
        # Anthropic
        anthropic_label = QLabel("Anthropic")
        anthropic_label.setObjectName("sectionTitle")
        layout.addWidget(anthropic_label)
        
        self.anthropic_key_input = QLineEdit()
        self.anthropic_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key_input.setPlaceholderText("sk-ant-...")
        if self.user_config.anthropic_api_key:
            self.anthropic_key_input.setText(self.user_config.anthropic_api_key)
        layout.addWidget(self.anthropic_key_input)
        
        layout.addSpacing(16)
        
        # Save button
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("保存")
        save_btn.setObjectName("primary")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_api_keys)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)
        
        layout.addStretch()
        self.page_stack.addWidget(page)
    
    def _on_nav_changed(self, index: int):
        """Handle navigation change."""
        self.page_stack.setCurrentIndex(index)
    
    def _on_position_btn_clicked(self, position: str):
        """Handle position button click."""
        self.overlay.set_position(position)
        self.user_config.update(overlay_position=position)
    
    def _get_pos_label(self, pos: str) -> str:
        """Get Japanese label for position."""
        labels = {
            "top-left": "左上",
            "top-center": "上中央", 
            "top-right": "右上",
            "bottom-left": "左下",
            "bottom-center": "下中央",
            "bottom-right": "右下"
        }
        return labels.get(pos, pos)
    
    def _on_inline_hotkey_captured(self, hotkey: str):
        """Handle inline hotkey capture."""
        if hotkey:
            self.hotkey_config.key = hotkey
            self.hotkey_manager.update_hotkey(hotkey)
            self.user_config.update(hotkey=hotkey)
    
    def _set_hotkey_preset(self, key: str):
        """Set a preset hotkey."""
        self.hotkey_input.setText(key)
        self.hotkey_config.key = key
        self.hotkey_manager.update_hotkey(key)
        self.user_config.update(hotkey=key)
    
    def _setup_overlay(self):
        """Setup the overlay indicator."""
        self.overlay = OverlayIndicator(position=self.user_config.overlay_position)
        
        # Connect overlay signals
        self.overlay.recording_toggled.connect(self._toggle_recording)
        self.overlay.settings_requested.connect(self._show_settings)
        self.overlay.quit_requested.connect(self._quit_app)
        
        self.overlay.show_indicator()
    
    def _setup_tray(self):
        """Setup system tray icon."""
        # Create icons
        self._icon_normal = create_tray_icon()
        self._icon_recording = create_recording_icon()
        self._icon_processing = create_processing_icon()
        
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self._icon_normal)
        self.tray_icon.setToolTip("Chotto Voice 🎤")
        
        # Tray menu
        tray_menu = QMenu()
        
        # Recording control
        self.tray_record_action = QAction("🎤 録音開始", self)
        self.tray_record_action.triggered.connect(self._toggle_recording)
        tray_menu.addAction(self.tray_record_action)
        
        tray_menu.addSeparator()
        
        # Settings
        settings_action = QAction("⚙️ 設定", self)
        settings_action.triggered.connect(self._show_settings)
        tray_menu.addAction(settings_action)
        
        tray_menu.addSeparator()
        
        # Quit
        quit_action = QAction("終了", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()
        
        # Show startup notification
        self.tray_icon.showMessage(
            "Chotto Voice",
            f"システムトレイで起動しました\nホットキー: {self.hotkey_config.key}",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )
    
    def _toggle_recording(self):
        """Toggle recording state."""
        if self.recorder.is_recording:
            self._stop_recording()
        else:
            self._start_recording()
    
    def _start_recording(self):
        """Start recording."""
        # Check if transcriber is available
        if self.transcriber is None:
            self.status_label.setText("❌ 音声認識が設定されていません（APIキーを確認）")
            self.status_label.setStyleSheet("color: red;")
            return
        
        # Fade out system audio
        self.audio_controller.fade_out(duration=0.3)
        
        self.recorder.on_audio_level = self._update_audio_level
        self.recorder.start_recording()
        
        self.record_btn.setText("⏹️ 録音停止")
        self.record_btn.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                background-color: #f44336;
                color: white;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.status_label.setText("🔴 録音中...")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.result_text.clear()
        
        # Update tray and overlay
        self.tray_record_action.setText("⏹️ 録音停止")
        self.tray_icon.setIcon(self._icon_recording)
        self.tray_icon.setToolTip("Chotto Voice 🔴 録音中...")
        self.overlay.set_state("recording")
        
        # Sync hotkey manager state
        self.hotkey_manager.set_recording_state(True)
    
    def _stop_recording(self):
        """Stop recording and process."""
        audio_data = self.recorder.stop_recording()
        
        # Fade in system audio
        self.audio_controller.fade_in(duration=0.3)
        
        self.record_btn.setText("🎤 録音開始")
        self.record_btn.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                background-color: #4CAF50;
                color: white;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.level_bar.setValue(0)
        
        # Update tray
        self.tray_record_action.setText("🎤 録音開始")
        
        # Sync hotkey manager state
        self.hotkey_manager.set_recording_state(False)
        
        if audio_data:
            # Go directly to processing state (skip idle to avoid animation glitch)
            self.status_label.setText("⏳ 処理中...")
            self.status_label.setStyleSheet("color: orange;")
            self.record_btn.setEnabled(False)
            self.tray_icon.setIcon(self._icon_processing)
            self.tray_icon.setToolTip("Chotto Voice ⏳ 処理中...")
            self.overlay.set_state("processing")
            
            # Start worker
            self._worker = TranscriptionWorker(
                self.transcriber,
                self.ai_client,
                audio_data,
                self._process_with_ai and self.ai_client is not None
            )
            self._worker.transcription_done.connect(self._on_transcription_done)
            self._worker.ai_chunk.connect(self._on_ai_chunk)
            self._worker.finished.connect(self._on_finished)
            self._worker.error.connect(self._on_error)
            self._worker.start()
        else:
            # No audio data - go to idle state
            self.tray_icon.setIcon(self._icon_normal)
            self.tray_icon.setToolTip("Chotto Voice 🎤")
            self.overlay.set_state("idle")
            self.status_label.setText("音声が検出されませんでした")
            self.status_label.setStyleSheet("color: gray;")
    
    def _update_audio_level(self, level: float):
        """Update audio level indicator."""
        scaled = min(int(level * 1000), 100)
        self.level_bar.setValue(scaled)
        # Also update overlay waveform
        self.overlay.set_audio_level(level * 10)  # Scale for visibility
    
    def _on_transcription_done(self, text: str):
        """Handle transcription completion."""
        # Only show if not processing with AI (AI will replace it)
        if text and not (self._process_with_ai and self.ai_client):
            self.result_text.setText(text)
        self._final_result = text
    
    def _on_ai_chunk(self, chunk: str):
        """Handle AI response chunk - update result with AI processed text."""
        # First chunk - clear the display
        if not hasattr(self, '_ai_receiving'):
            self._ai_receiving = True
            self.result_text.clear()
        self.result_text.insertPlainText(chunk)
    
    def _on_finished(self, text: str):
        """Handle processing completion."""
        self.record_btn.setEnabled(True)
        self.status_label.setText("✅ 完了")
        self.status_label.setStyleSheet("color: green;")
        
        # Reset flags
        if hasattr(self, '_ai_receiving'):
            delattr(self, '_ai_receiving')
        
        # Only update if we weren't streaming (streaming already updated)
        if not self._process_with_ai or not self.ai_client:
            if text:
                self.result_text.setText(text)
        
        # Restore tray icon and overlay
        self.tray_icon.setIcon(self._icon_normal)
        self.tray_icon.setToolTip("Chotto Voice 🎤")
        self.overlay.set_state("idle")
        
        print(f"[Finished] text='{text[:30] if text else '(empty)'}...', auto_type={self._auto_type}", flush=True)
        if text and self._auto_type:
            # Small delay then type to focused field
            QTimer.singleShot(100, lambda: self._type_result(text))
    
    def _type_result(self, text: str):
        """Type result to focused field."""
        print(f"[TypeResult] Typing: '{text[:30] if text else '(empty)'}...'", flush=True)
        try:
            type_to_focused_field(text)
            print("[TypeResult] Success", flush=True)
            self.status_label.setText("✅ 入力完了")
        except Exception as e:
            print(f"[TypeResult] Error: {e}", flush=True)
            self.status_label.setText(f"入力エラー: {e}")
            self.status_label.setStyleSheet("color: red;")
    
    def _on_error(self, error: str):
        """Handle error."""
        self.record_btn.setEnabled(True)
        self.status_label.setText(f"❌ エラー: {error}")
        self.status_label.setStyleSheet("color: red;")
        
        # Restore tray icon and overlay
        self.tray_icon.setIcon(self._icon_normal)
        self.tray_icon.setToolTip("Chotto Voice 🎤")
        self.overlay.set_state("idle")
    
    # === Hotkey callbacks ===
    
    def _on_hotkey_record_start(self):
        """Called when hotkey triggers record start."""
        self._start_recording_signal.emit()
    
    def _on_hotkey_record_stop(self):
        """Called when hotkey triggers record stop."""
        self._stop_recording_signal.emit()
    
    def _on_hotkey_mute_toggle(self, should_mute: bool):
        """Called when hotkey triggers mute toggle."""
        if should_mute:
            self._was_muted_before_recording = self.audio_controller.is_muted()
            self.audio_controller.mute()
        else:
            if not self._was_muted_before_recording:
                self.audio_controller.unmute()
        
        self._mute_changed_signal.emit(should_mute)
    
    def _update_mute_status(self, is_muted: bool):
        """Update mute indicator."""
        self.mute_indicator.setText("🔇" if is_muted else "🔊")
    
    def _save_api_keys(self):
        """Save API keys and reinitialize clients."""
        openai_key = self.openai_key_input.text().strip()
        anthropic_key = self.anthropic_key_input.text().strip()
        gemini_key = self.gemini_key_input.text().strip()
        
        # Save to config
        self.user_config.update(
            openai_api_key=openai_key,
            anthropic_api_key=anthropic_key,
            gemini_api_key=gemini_key
        )
        
        # Reinitialize transcriber if OpenAI key provided
        if openai_key:
            try:
                from ..transcriber import create_transcriber
                self.transcriber = create_transcriber(
                    provider="openai_api",
                    api_key=openai_key,
                    model="whisper-1"
                )
                self.record_btn.setEnabled(True)
                self.status_label.setText("✅ APIキー保存完了")
                self.status_label.setStyleSheet("color: green;")
            except Exception as e:
                self.status_label.setText(f"❌ Transcriber初期化エラー: {e}")
                self.status_label.setStyleSheet("color: red;")
        
        # Reinitialize AI client (prefer Gemini=free, then Anthropic, then OpenAI)
        self.ai_client = None
        if gemini_key:
            try:
                from ..ai_client import create_ai_client
                self.ai_client = create_ai_client(
                    provider="gemini",
                    api_key=gemini_key,
                    model="gemini-2.0-flash"
                )
                self.ai_process_check.setEnabled(True)
                print("AI client: Google Gemini")
            except Exception as e:
                print(f"Gemini client error: {e}")
        
        if not self.ai_client and anthropic_key:
            try:
                from ..ai_client import create_ai_client
                self.ai_client = create_ai_client(
                    provider="claude",
                    api_key=anthropic_key,
                    model="claude-sonnet-4-20250514"
                )
                self.ai_process_check.setEnabled(True)
                print("AI client: Claude")
            except Exception as e:
                print(f"Claude client error: {e}")
        
        if not self.ai_client and openai_key:
            try:
                from ..ai_client import create_ai_client
                self.ai_client = create_ai_client(
                    provider="openai",
                    api_key=openai_key,
                    model="gpt-4o"
                )
                self.ai_process_check.setEnabled(True)
                print("AI client: OpenAI GPT")
            except Exception as e:
                print(f"AI client error: {e}")
        
        # Show notification
        self.tray_icon.showMessage(
            "Chotto Voice",
            "APIキーを保存しました。",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )
    
    def _on_auto_type_changed(self, checked: bool):
        """Handle auto-type checkbox change."""
        self._auto_type = checked
        self.user_config.update(auto_type=checked)
    
    def _on_ai_process_changed(self, checked: bool):
        """Handle AI process checkbox change."""
        self._process_with_ai = checked
        self.user_config.update(process_with_ai=checked)
    
    def _on_startup_changed(self, checked: bool):
        """Handle Windows startup checkbox change."""
        success = set_startup_enabled(checked)
        if not success:
            # Revert checkbox if failed
            self.startup_check.blockSignals(True)
            self.startup_check.setChecked(not checked)
            self.startup_check.blockSignals(False)
            self.tray_icon.showMessage(
                "Chotto Voice",
                "スタートアップ設定に失敗しました",
                QSystemTrayIcon.MessageIcon.Warning,
                2000
            )
        else:
            self.user_config.update(start_with_windows=checked)
    
    def _on_overlay_position_changed(self, index: int):
        """Handle overlay position change."""
        position = self.overlay_position_combo.itemData(index)
        self.overlay.set_position(position)
        self.user_config.update(overlay_position=position)
    
    def _on_whisper_provider_changed(self, index: int):
        """Handle Whisper provider change."""
        provider = self.whisper_provider_combo.itemData(index)
        self.user_config.update(whisper_provider=provider)
        
        # Enable/disable model combo
        self.whisper_model_combo.setEnabled(provider == "local")
        
        # Reinitialize transcriber
        self._reinit_transcriber()
    
    def _on_whisper_model_changed(self, index: int):
        """Handle Whisper model change."""
        model = self.whisper_model_combo.itemData(index)
        self.user_config.update(whisper_local_model=model)
        
        # Reinitialize transcriber if using local
        if self.user_config.whisper_provider == "local":
            self._reinit_transcriber()
    
    def _reinit_transcriber(self):
        """Reinitialize transcriber based on current settings."""
        provider = self.user_config.whisper_provider
        
        if provider == "local":
            try:
                from ..transcriber import create_transcriber
                model = self.user_config.whisper_local_model
                self.transcriber = create_transcriber(
                    provider="local",
                    model=model
                )
                self.record_btn.setEnabled(True)
                self.status_label.setText(f"✅ ローカルWhisper ({model})")
                self.status_label.setStyleSheet("color: green;")
            except Exception as e:
                self.status_label.setText(f"❌ Whisperエラー: {e}")
                self.status_label.setStyleSheet("color: red;")
        else:  # API
            openai_key = self.user_config.openai_api_key
            if openai_key:
                try:
                    from ..transcriber import create_transcriber
                    self.transcriber = create_transcriber(
                        provider="openai_api",
                        api_key=openai_key,
                        model="whisper-1"
                    )
                    self.record_btn.setEnabled(True)
                    self.status_label.setText("✅ Whisper API")
                    self.status_label.setStyleSheet("color: green;")
                except Exception as e:
                    self.status_label.setText(f"❌ API エラー: {e}")
                    self.status_label.setStyleSheet("color: red;")
            else:
                self.status_label.setText("⚠️ OpenAI APIキーが必要です")
                self.status_label.setStyleSheet("color: orange;")
    
    def _open_hotkey_settings(self):
        """Open hotkey settings dialog."""
        # Temporarily disable hotkey listening
        self.hotkey_manager.stop()
        
        dialog = HotkeySettingsDialog(self.hotkey_config.key, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_hotkey = dialog.get_hotkey()
            if new_hotkey:
                self.hotkey_config.key = new_hotkey
                self.hotkey_manager.update_hotkey(new_hotkey)
                self.hotkey_label.setText(f"⌨️ ホットキー: {new_hotkey}")
                # Save to persistent config
                self.user_config.update(hotkey=new_hotkey)
        
        # Re-enable hotkey listening
        self.hotkey_manager.start()
    
    def _show_settings(self):
        """Show the settings window."""
        self.show()
        self.activateWindow()
        self.raise_()
    
    def _tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_settings()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click - could toggle recording
            pass
    
    def closeEvent(self, event: QCloseEvent):
        """Handle close event - minimize to tray."""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Chotto Voice",
            "システムトレイで動作中",
            QSystemTrayIcon.MessageIcon.Information,
            1500
        )
    
    def _quit_app(self):
        """Quit the application."""
        self.hotkey_manager.stop()
        
        if self.hotkey_manager.is_muted:
            if not self._was_muted_before_recording:
                self.audio_controller.unmute()
        
        self.tray_icon.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()
