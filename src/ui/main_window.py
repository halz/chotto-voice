"""Main window for Chotto Voice."""
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QProgressBar,
    QSystemTrayIcon, QMenu, QComboBox, QGroupBox,
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QCheckBox
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
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("クリックしてキーを押す...")
        self.setReadOnly(True)
        self._capturing = False
        self._modifiers = set()
    
    def focusInEvent(self, event):
        """Start capturing when focused."""
        super().focusInEvent(event)
        self._capturing = True
        self._modifiers = set()
        self.setText("")
        self.setStyleSheet("background-color: #fff3cd; border: 2px solid #ffc107;")
        self.setPlaceholderText("キーを押してください...")
    
    def focusOutEvent(self, event):
        """Stop capturing when focus lost."""
        super().focusOutEvent(event)
        self._capturing = False
        self.setStyleSheet("")
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
            self.setStyleSheet("background-color: #d4edda; border: 2px solid #28a745;")
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
        preset_layout = QHBoxLayout(preset_group)
        
        for name, key in list(HOTKEY_PRESETS.items())[:4]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, k=key: self._set_preset(k))
            preset_layout.addWidget(btn)
        
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
        self.hotkey_input.setStyleSheet("background-color: #d4edda; border: 2px solid #28a745;")
    
    def get_hotkey(self) -> str:
        return self._captured_hotkey or self.hotkey_input.text()


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
            # Step 1: Transcribe
            text = self.transcriber.transcribe(self.audio_data)
            self.transcription_done.emit(text)
            
            if not text:
                self.finished.emit("")
                return
            
            # Step 2: AI processing (if enabled and available)
            if self.process_with_ai and self.ai_client:
                result_text = ""
                for chunk in self.ai_client.process_stream(text):
                    self.ai_chunk.emit(chunk)
                    result_text += chunk
                self.finished.emit(result_text)
            else:
                self.finished.emit(text)
                
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""
    
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
    
    def _setup_ui(self):
        """Setup the user interface (Settings window)."""
        self.setWindowTitle("Chotto Voice - 設定")
        self.setMinimumSize(450, 350)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Recording section
        record_group = QGroupBox("録音")
        record_layout = QVBoxLayout(record_group)
        
        # Record button
        self.record_btn = QPushButton("🎤 録音開始")
        self.record_btn.setMinimumHeight(80)
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
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.record_btn.clicked.connect(self._toggle_recording)
        record_layout.addWidget(self.record_btn)
        
        # Audio level indicator
        self.level_bar = QProgressBar()
        self.level_bar.setMaximum(100)
        self.level_bar.setTextVisible(False)
        self.level_bar.setMaximumHeight(8)
        record_layout.addWidget(self.level_bar)
        
        # Status label
        self.status_label = QLabel("準備完了")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: gray;")
        record_layout.addWidget(self.status_label)
        
        layout.addWidget(record_group)
        
        # Result display (simplified)
        result_group = QGroupBox("結果")
        result_layout = QVBoxLayout(result_group)
        
        self.result_text = QTextEdit()
        self.result_text.setPlaceholderText("音声認識の結果がここに表示されます...")
        self.result_text.setMaximumHeight(120)
        result_layout.addWidget(self.result_text)
        
        layout.addWidget(result_group)
        
        # Options
        options_layout = QHBoxLayout()
        
        self.auto_type_check = QCheckBox("フォーカス中のフィールドに入力")
        self.auto_type_check.setChecked(self._auto_type)
        self.auto_type_check.toggled.connect(self._on_auto_type_changed)
        options_layout.addWidget(self.auto_type_check)
        
        self.ai_process_check = QCheckBox("AIで整形")
        self.ai_process_check.setChecked(self._process_with_ai)
        self.ai_process_check.setEnabled(self.ai_client is not None)
        self.ai_process_check.toggled.connect(self._on_ai_process_changed)
        options_layout.addWidget(self.ai_process_check)
        
        layout.addLayout(options_layout)
        
        # Startup options (Windows only)
        if sys.platform == "win32":
            startup_layout = QHBoxLayout()
            
            self.startup_check = QCheckBox("Windowsと一緒に起動")
            self.startup_check.setChecked(is_startup_enabled())
            self.startup_check.toggled.connect(self._on_startup_changed)
            startup_layout.addWidget(self.startup_check)
            
            startup_layout.addStretch()
            
            layout.addLayout(startup_layout)
        
        # Hotkey settings
        hotkey_layout = QHBoxLayout()
        
        self.hotkey_label = QLabel(f"⌨️ ホットキー: {self.hotkey_config.key}")
        hotkey_layout.addWidget(self.hotkey_label)
        
        hotkey_layout.addStretch()
        
        self.mute_indicator = QLabel("🔊")
        self.mute_indicator.setStyleSheet("font-size: 18px;")
        hotkey_layout.addWidget(self.mute_indicator)
        
        self.hotkey_btn = QPushButton("⚙️")
        self.hotkey_btn.setMaximumWidth(40)
        self.hotkey_btn.clicked.connect(self._open_hotkey_settings)
        hotkey_layout.addWidget(self.hotkey_btn)
        
        layout.addLayout(hotkey_layout)
    
    def _setup_overlay(self):
        """Setup the overlay indicator."""
        self.overlay = OverlayIndicator(size=24)
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
    
    def _stop_recording(self):
        """Stop recording and process."""
        audio_data = self.recorder.stop_recording()
        
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
        
        # Update tray and overlay
        self.tray_record_action.setText("🎤 録音開始")
        self.tray_icon.setIcon(self._icon_normal)
        self.tray_icon.setToolTip("Chotto Voice 🎤")
        self.overlay.set_state("idle")
        
        if audio_data:
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
            self.status_label.setText("音声が検出されませんでした")
            self.status_label.setStyleSheet("color: gray;")
    
    def _update_audio_level(self, level: float):
        """Update audio level indicator."""
        scaled = min(int(level * 1000), 100)
        self.level_bar.setValue(scaled)
    
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
        
        if text and self._auto_type:
            # Small delay then type to focused field
            QTimer.singleShot(100, lambda: self._type_result(text))
    
    def _type_result(self, text: str):
        """Type result to focused field."""
        try:
            type_to_focused_field(text)
            self.status_label.setText("✅ 入力完了")
        except Exception as e:
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
