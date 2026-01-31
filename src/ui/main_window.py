"""Main window for Chotto Voice."""
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QProgressBar,
    QSystemTrayIcon, QMenu, QComboBox, QGroupBox,
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMetaObject, Q_ARG
from PyQt6.QtGui import QIcon, QAction, QCloseEvent

from ..audio import AudioRecorder
from ..transcriber import Transcriber
from ..ai_client import AIClient
from ..hotkey import HotkeyManager, HotkeyConfig, HOTKEY_PRESETS
from ..audio_control import get_audio_controller, AudioController


class TranscriptionWorker(QThread):
    """Worker thread for transcription."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, transcriber: Transcriber, audio_data: bytes):
        super().__init__()
        self.transcriber = transcriber
        self.audio_data = audio_data
    
    def run(self):
        try:
            text = self.transcriber.transcribe(self.audio_data)
            self.finished.emit(text)
        except Exception as e:
            self.error.emit(str(e))


class AIProcessWorker(QThread):
    """Worker thread for AI processing."""
    chunk_received = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, ai_client: AIClient, text: str):
        super().__init__()
        self.ai_client = ai_client
        self.text = text
    
    def run(self):
        try:
            for chunk in self.ai_client.process_stream(self.text):
                self.chunk_received.emit(chunk)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class HotkeySettingsDialog(QDialog):
    """Dialog for configuring hotkey settings."""
    
    def __init__(self, current_hotkey: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ホットキー設定")
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        
        # Preset selection
        form = QFormLayout()
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("カスタム", "")
        for name, key in HOTKEY_PRESETS.items():
            self.preset_combo.addItem(name, key)
        form.addRow("プリセット:", self.preset_combo)
        
        # Custom hotkey input
        self.hotkey_input = QLineEdit(current_hotkey)
        self.hotkey_input.setPlaceholderText("例: ctrl+shift+space")
        form.addRow("ホットキー:", self.hotkey_input)
        
        layout.addLayout(form)
        
        # Instructions
        help_label = QLabel(
            "📌 使い方:\n"
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
        
        # Connect preset selection
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
    
    def _on_preset_changed(self, index: int):
        key = self.preset_combo.currentData()
        if key:
            self.hotkey_input.setText(key)
    
    def get_hotkey(self) -> str:
        return self.hotkey_input.text()


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
        hotkey_config: Optional[HotkeyConfig] = None
    ):
        super().__init__()
        self.recorder = recorder
        self.transcriber = transcriber
        self.ai_client = ai_client
        
        self._transcription_worker: Optional[TranscriptionWorker] = None
        self._ai_worker: Optional[AIProcessWorker] = None
        
        # Audio controller for muting
        self.audio_controller: AudioController = get_audio_controller()
        self._was_muted_before_recording = False
        
        # Setup hotkey manager
        self.hotkey_config = hotkey_config or HotkeyConfig()
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
        
        # Start hotkey listening
        self.hotkey_manager.start()
    
    def _setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("Chotto Voice 🎤")
        self.setMinimumSize(500, 400)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Recording section
        record_group = QGroupBox("録音")
        record_layout = QVBoxLayout(record_group)
        
        # Record button
        self.record_btn = QPushButton("🎤 録音開始")
        self.record_btn.setMinimumHeight(60)
        self.record_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                background-color: #4CAF50;
                color: white;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.record_btn.clicked.connect(self._toggle_recording)
        record_layout.addWidget(self.record_btn)
        
        # Audio level indicator
        self.level_bar = QProgressBar()
        self.level_bar.setMaximum(100)
        self.level_bar.setTextVisible(False)
        self.level_bar.setMaximumHeight(10)
        record_layout.addWidget(self.level_bar)
        
        layout.addWidget(record_group)
        
        # Transcription output
        trans_group = QGroupBox("音声認識結果")
        trans_layout = QVBoxLayout(trans_group)
        
        self.transcription_text = QTextEdit()
        self.transcription_text.setPlaceholderText("音声認識の結果がここに表示されます...")
        self.transcription_text.setMaximumHeight(100)
        trans_layout.addWidget(self.transcription_text)
        
        layout.addWidget(trans_group)
        
        # AI Response
        ai_group = QGroupBox("AI応答")
        ai_layout = QVBoxLayout(ai_group)
        
        self.ai_response_text = QTextEdit()
        self.ai_response_text.setPlaceholderText("AIの応答がここに表示されます...")
        self.ai_response_text.setReadOnly(True)
        ai_layout.addWidget(self.ai_response_text)
        
        # Process with AI button
        self.process_btn = QPushButton("🤖 AIで処理")
        self.process_btn.clicked.connect(self._process_with_ai)
        self.process_btn.setEnabled(False)
        ai_layout.addWidget(self.process_btn)
        
        layout.addWidget(ai_group)
        
        # Hotkey settings
        hotkey_group = QGroupBox("ホットキー")
        hotkey_layout = QHBoxLayout(hotkey_group)
        
        self.hotkey_label = QLabel(f"現在: {self.hotkey_config.key}")
        hotkey_layout.addWidget(self.hotkey_label)
        
        self.hotkey_btn = QPushButton("⚙️ 変更")
        self.hotkey_btn.clicked.connect(self._open_hotkey_settings)
        hotkey_layout.addWidget(self.hotkey_btn)
        
        self.mute_indicator = QLabel("🔊")
        self.mute_indicator.setStyleSheet("font-size: 20px;")
        hotkey_layout.addWidget(self.mute_indicator)
        
        layout.addWidget(hotkey_group)
        
        # Status bar
        self.statusBar().showMessage(f"準備完了 | ホットキー: {self.hotkey_config.key}")
    
    def _setup_tray(self):
        """Setup system tray icon."""
        self.tray_icon = QSystemTrayIcon(self)
        # TODO: Add actual icon
        # self.tray_icon.setIcon(QIcon("assets/icon.png"))
        
        # Tray menu
        tray_menu = QMenu()
        
        show_action = QAction("表示", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        quit_action = QAction("終了", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()
    
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
                font-size: 18px;
                background-color: #f44336;
                color: white;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.statusBar().showMessage("録音中...")
    
    def _stop_recording(self):
        """Stop recording and transcribe."""
        audio_data = self.recorder.stop_recording()
        
        self.record_btn.setText("🎤 録音開始")
        self.record_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                background-color: #4CAF50;
                color: white;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.level_bar.setValue(0)
        
        if audio_data:
            self.statusBar().showMessage("音声認識中...")
            self.record_btn.setEnabled(False)
            
            self._transcription_worker = TranscriptionWorker(
                self.transcriber, audio_data
            )
            self._transcription_worker.finished.connect(self._on_transcription_done)
            self._transcription_worker.error.connect(self._on_transcription_error)
            self._transcription_worker.start()
        else:
            self.statusBar().showMessage("音声が検出されませんでした")
    
    def _update_audio_level(self, level: float):
        """Update audio level indicator."""
        # Scale level (0-1) to progress bar (0-100)
        scaled = min(int(level * 1000), 100)
        self.level_bar.setValue(scaled)
    
    def _on_transcription_done(self, text: str):
        """Handle transcription completion."""
        self.transcription_text.setText(text)
        self.record_btn.setEnabled(True)
        self.process_btn.setEnabled(bool(text and self.ai_client))
        self.statusBar().showMessage("音声認識完了")
    
    def _on_transcription_error(self, error: str):
        """Handle transcription error."""
        self.statusBar().showMessage(f"エラー: {error}")
        self.record_btn.setEnabled(True)
    
    def _process_with_ai(self):
        """Process transcription with AI."""
        text = self.transcription_text.toPlainText()
        if not text or not self.ai_client:
            return
        
        self.ai_response_text.clear()
        self.process_btn.setEnabled(False)
        self.statusBar().showMessage("AI処理中...")
        
        self._ai_worker = AIProcessWorker(self.ai_client, text)
        self._ai_worker.chunk_received.connect(self._on_ai_chunk)
        self._ai_worker.finished.connect(self._on_ai_done)
        self._ai_worker.error.connect(self._on_ai_error)
        self._ai_worker.start()
    
    def _on_ai_chunk(self, chunk: str):
        """Handle AI response chunk."""
        self.ai_response_text.insertPlainText(chunk)
    
    def _on_ai_done(self):
        """Handle AI processing completion."""
        self.process_btn.setEnabled(True)
        self.statusBar().showMessage("AI処理完了")
    
    def _on_ai_error(self, error: str):
        """Handle AI processing error."""
        self.statusBar().showMessage(f"AIエラー: {error}")
        self.process_btn.setEnabled(True)
    
    # === Hotkey callbacks ===
    
    def _on_hotkey_record_start(self):
        """Called when hotkey triggers record start (from another thread)."""
        self._start_recording_signal.emit()
    
    def _on_hotkey_record_stop(self):
        """Called when hotkey triggers record stop (from another thread)."""
        self._stop_recording_signal.emit()
    
    def _on_hotkey_mute_toggle(self, should_mute: bool):
        """Called when hotkey triggers mute toggle (from another thread)."""
        if should_mute:
            self._was_muted_before_recording = self.audio_controller.is_muted()
            self.audio_controller.mute()
        else:
            # Restore previous mute state
            if not self._was_muted_before_recording:
                self.audio_controller.unmute()
        
        self._mute_changed_signal.emit(should_mute)
    
    def _update_mute_status(self, is_muted: bool):
        """Update mute indicator in UI."""
        self.mute_indicator.setText("🔇" if is_muted else "🔊")
        status = "ミュート中" if is_muted else "ミュート解除"
        self.statusBar().showMessage(f"{status} | ホットキー: {self.hotkey_config.key}")
    
    def _open_hotkey_settings(self):
        """Open hotkey settings dialog."""
        dialog = HotkeySettingsDialog(self.hotkey_config.key, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_hotkey = dialog.get_hotkey()
            if new_hotkey:
                self.hotkey_config.key = new_hotkey
                self.hotkey_manager.update_hotkey(new_hotkey)
                self.hotkey_label.setText(f"現在: {new_hotkey}")
                self.statusBar().showMessage(f"ホットキーを変更: {new_hotkey}")
    
    def _tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()
    
    def closeEvent(self, event: QCloseEvent):
        """Handle close event - minimize to tray."""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Chotto Voice",
            "システムトレイで動作中です",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )
    
    def _quit_app(self):
        """Quit the application."""
        # Cleanup
        self.hotkey_manager.stop()
        
        # Restore audio if muted
        if self.hotkey_manager.is_muted:
            if not self._was_muted_before_recording:
                self.audio_controller.unmute()
        
        self.tray_icon.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()
