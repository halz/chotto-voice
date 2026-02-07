"""Overlay indicator for Chotto Voice - iOS-style recording indicator."""
from PyQt6.QtWidgets import QWidget, QApplication, QMenu
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPainterPath, QAction, QCursor
import time
import random


# Position options
OVERLAY_POSITIONS = {
    "top-left": "左上",
    "top-center": "上中央",
    "top-right": "右上",
    "bottom-left": "左下",
    "bottom-center": "下中央",
    "bottom-right": "右下",
}


class OverlayIndicator(QWidget):
    """iOS-style overlay indicator with configurable position."""
    
    # Signals for menu actions
    recording_toggled = pyqtSignal()
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    
    # Sizes (smaller)
    IDLE_WIDTH = 44
    IDLE_HEIGHT = 22
    RECORDING_WIDTH = 220
    RECORDING_HEIGHT = 36
    
    MARGIN = 20  # Margin from screen edges
    
    # Colors
    BG_COLOR = QColor(45, 45, 48, 230)  # Dark gray, slightly transparent
    IDLE_DOT_COLOR = QColor(100, 100, 120)  # Muted blue-gray
    MIC_BG_COLOR = QColor(220, 50, 47)  # Red
    MIC_ICON_COLOR = QColor(255, 255, 255)  # White
    WAVEFORM_COLOR = QColor(180, 180, 180)  # Light gray
    TIMER_COLOR = QColor(160, 160, 160)  # Gray
    PROCESSING_COLOR = QColor(255, 152, 0)  # Orange
    
    def __init__(self, position: str = "bottom-right"):
        super().__init__()
        self._state = "idle"  # idle, recording, processing
        self._position = position
        self._recording_start_time = 0
        self._audio_levels = [0.1] * 30  # Waveform data (fewer bars for smaller size)
        self._current_width = float(self.IDLE_WIDTH)
        self._current_height = float(self.IDLE_HEIGHT)
        self._target_width = float(self.IDLE_WIDTH)
        self._target_height = float(self.IDLE_HEIGHT)
        self._pulse_opacity = 1.0
        self._pulse_direction = -1
        
        self._setup_window()
        self._setup_timers()
        self._setup_animations()
        self._setup_context_menu()
        self._position_window()
    
    # Properties for animation
    @pyqtProperty(float)
    def animatedWidth(self):
        return self._current_width
    
    @animatedWidth.setter
    def animatedWidth(self, value):
        self._current_width = value
        self.setFixedSize(int(self._current_width), int(self._current_height))
        self._position_window()
        self.update()
    
    @pyqtProperty(float)
    def animatedHeight(self):
        return self._current_height
    
    @animatedHeight.setter
    def animatedHeight(self, value):
        self._current_height = value
        self.setFixedSize(int(self._current_width), int(self._current_height))
        self._position_window()
        self.update()
    
    def _setup_window(self):
        """Configure window properties."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # Don't show in taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(int(self._current_width), int(self._current_height))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
    
    def _setup_timers(self):
        """Setup animation timers."""
        # Timer update (every 100ms)
        self._timer_update = QTimer(self)
        self._timer_update.timeout.connect(self._update_timer)
        self._timer_update.setInterval(100)
        
        # Waveform animation (30 FPS)
        self._waveform_timer = QTimer(self)
        self._waveform_timer.timeout.connect(self._update_waveform)
        self._waveform_timer.setInterval(33)
        
        # Pulse animation for processing state
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._pulse_timer.setInterval(50)
    
    def _setup_animations(self):
        """Setup size transition animations."""
        # Width animation
        self._width_anim = QPropertyAnimation(self, b"animatedWidth")
        self._width_anim.setDuration(200)  # 200ms
        self._width_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Height animation
        self._height_anim = QPropertyAnimation(self, b"animatedHeight")
        self._height_anim.setDuration(200)  # 200ms
        self._height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def _setup_context_menu(self):
        """Setup right-click context menu."""
        self._context_menu = QMenu(self)
        
        # Recording control
        self._record_action = QAction("🎤 録音開始", self)
        self._record_action.triggered.connect(self.recording_toggled.emit)
        self._context_menu.addAction(self._record_action)
        
        self._context_menu.addSeparator()
        
        # Settings
        settings_action = QAction("⚙️ 設定", self)
        settings_action.triggered.connect(self.settings_requested.emit)
        self._context_menu.addAction(settings_action)
        
        self._context_menu.addSeparator()
        
        # Quit
        quit_action = QAction("終了", self)
        quit_action.triggered.connect(self.quit_requested.emit)
        self._context_menu.addAction(quit_action)
    
    def _show_context_menu(self, pos):
        """Show context menu at cursor position."""
        # Update record action text based on state
        if self._state == "recording":
            self._record_action.setText("⏹️ 録音停止")
        else:
            self._record_action.setText("🎤 録音開始")
        
        self._context_menu.exec(QCursor.pos())
    
    def _update_size(self, animate: bool = True):
        """Update widget size based on state with optional animation."""
        if self._state == "idle":
            target_width = float(self.IDLE_WIDTH)
            target_height = float(self.IDLE_HEIGHT)
        else:
            target_width = float(self.RECORDING_WIDTH)
            target_height = float(self.RECORDING_HEIGHT)
        
        if animate and (target_width != self._current_width or target_height != self._current_height):
            # Animate size change
            self._width_anim.stop()
            self._height_anim.stop()
            
            self._width_anim.setStartValue(self._current_width)
            self._width_anim.setEndValue(target_width)
            
            self._height_anim.setStartValue(self._current_height)
            self._height_anim.setEndValue(target_height)
            
            self._width_anim.start()
            self._height_anim.start()
        else:
            # Set immediately (for initial setup)
            self._current_width = target_width
            self._current_height = target_height
            self.setFixedSize(int(self._current_width), int(self._current_height))
            self._position_window()
    
    def _position_window(self):
        """Position window based on configured position."""
        screen = QApplication.primaryScreen()
        if not screen:
            return
        
        geometry = screen.availableGeometry()
        w = int(self._current_width)
        h = int(self._current_height)
        m = self.MARGIN
        
        # Calculate position based on setting
        if self._position == "top-left":
            x = geometry.left() + m
            y = geometry.top() + m
        elif self._position == "top-center":
            x = geometry.left() + (geometry.width() - w) // 2
            y = geometry.top() + m
        elif self._position == "top-right":
            x = geometry.right() - w - m
            y = geometry.top() + m
        elif self._position == "bottom-left":
            x = geometry.left() + m
            y = geometry.bottom() - h - m
        elif self._position == "bottom-center":
            x = geometry.left() + (geometry.width() - w) // 2
            y = geometry.bottom() - h - m
        else:  # bottom-right (default)
            x = geometry.right() - w - m
            y = geometry.bottom() - h - m
        
        self.move(x, y)
    
    def set_position(self, position: str):
        """Set overlay position."""
        if position in OVERLAY_POSITIONS:
            self._position = position
            self._position_window()
    
    def _update_timer(self):
        """Update recording timer display."""
        self.update()
    
    def _update_waveform(self):
        """Update waveform animation."""
        # Shift waveform data left and add new random value
        self._audio_levels = self._audio_levels[1:] + [random.uniform(0.1, 0.8)]
        self.update()
    
    def _update_pulse(self):
        """Update pulse animation for processing."""
        self._pulse_opacity += self._pulse_direction * 0.05
        if self._pulse_opacity <= 0.4:
            self._pulse_opacity = 0.4
            self._pulse_direction = 1
        elif self._pulse_opacity >= 1.0:
            self._pulse_opacity = 1.0
            self._pulse_direction = -1
        self.update()
    
    def set_audio_level(self, level: float):
        """Update audio level for waveform (0.0 to 1.0)."""
        # Add real audio level to waveform
        self._audio_levels = self._audio_levels[1:] + [max(0.1, min(1.0, level))]
    
    def set_state(self, state: str):
        """Set indicator state: 'idle', 'recording', or 'processing'."""
        print(f"[Overlay] set_state: {self._state} -> {state}", flush=True)
        if self._state == state:
            print(f"[Overlay] State unchanged, skipping", flush=True)
            return
        
        self._state = state
        target_w = self.IDLE_WIDTH if state == "idle" else self.RECORDING_WIDTH
        target_h = self.IDLE_HEIGHT if state == "idle" else self.RECORDING_HEIGHT
        print(f"[Overlay] Target size: {target_w}x{target_h}", flush=True)
        self._update_size()
        
        if state == "recording":
            self._recording_start_time = time.time()
            self._audio_levels = [0.1] * 40  # Reset waveform
            self._timer_update.start()
            self._waveform_timer.start()
            self._pulse_timer.stop()
        elif state == "processing":
            self._timer_update.stop()
            self._waveform_timer.stop()
            self._pulse_timer.start()
        else:  # idle
            self._timer_update.stop()
            self._waveform_timer.stop()
            self._pulse_timer.stop()
            self._pulse_opacity = 1.0
        
        self.update()
    
    def _get_recording_time(self) -> str:
        """Get formatted recording time."""
        if self._recording_start_time == 0:
            return "0:00"
        elapsed = int(time.time() - self._recording_start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        return f"{minutes}:{seconds:02d}"
    
    def paintEvent(self, event):
        """Draw the indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self._state == "idle":
            self._draw_idle(painter)
        elif self._state == "recording":
            self._draw_recording(painter)
        elif self._state == "processing":
            self._draw_processing(painter)
    
    def _draw_idle(self, painter: QPainter):
        """Draw idle state - small pill with dot."""
        # Draw pill background
        path = QPainterPath()
        rect = QRectF(0, 0, self._current_width, self._current_height)
        path.addRoundedRect(rect, self._current_height / 2, self._current_height / 2)
        
        painter.setBrush(QBrush(self.BG_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
        
        # Draw center dot
        dot_size = 6
        dot_x = (self._current_width - dot_size) / 2
        dot_y = (self._current_height - dot_size) / 2
        painter.setBrush(QBrush(self.IDLE_DOT_COLOR))
        painter.drawEllipse(QRectF(dot_x, dot_y, dot_size, dot_size))
    
    def _draw_recording(self, painter: QPainter):
        """Draw recording state - pill with mic, waveform, timer."""
        # Draw pill background
        path = QPainterPath()
        rect = QRectF(0, 0, self._current_width, self._current_height)
        path.addRoundedRect(rect, self._current_height / 2, self._current_height / 2)
        
        painter.setBrush(QBrush(self.BG_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
        
        # Draw microphone icon with red background
        mic_margin = 4
        mic_size = self._current_height - mic_margin * 2
        mic_x = mic_margin
        mic_y = mic_margin
        
        # Red circle background
        painter.setBrush(QBrush(self.MIC_BG_COLOR))
        painter.drawEllipse(QRectF(mic_x, mic_y, mic_size, mic_size))
        
        # Microphone icon (simplified)
        painter.setPen(QPen(self.MIC_ICON_COLOR, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        mic_center_x = mic_x + mic_size / 2
        mic_center_y = mic_y + mic_size / 2
        
        # Mic body (rounded rectangle)
        mic_body_w = mic_size * 0.28
        mic_body_h = mic_size * 0.4
        mic_body_rect = QRectF(
            mic_center_x - mic_body_w / 2,
            mic_center_y - mic_body_h / 2 - 1,
            mic_body_w,
            mic_body_h
        )
        painter.drawRoundedRect(mic_body_rect, mic_body_w / 2, mic_body_w / 2)
        
        # Mic stand arc
        arc_rect = QRectF(
            mic_center_x - mic_size * 0.22,
            mic_center_y - mic_size * 0.1,
            mic_size * 0.44,
            mic_size * 0.35
        )
        painter.drawArc(arc_rect, 0, -180 * 16)
        
        # Mic stand line
        painter.drawLine(
            QPointF(mic_center_x, mic_center_y + mic_size * 0.22),
            QPointF(mic_center_x, mic_center_y + mic_size * 0.32)
        )
        
        # Draw waveform
        waveform_start = mic_x + mic_size + 8
        waveform_end = self._current_width - 42
        waveform_width = waveform_end - waveform_start
        bar_count = len(self._audio_levels)
        bar_width = 2
        bar_spacing = max(1, (waveform_width - bar_count * bar_width) / max(1, bar_count - 1))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.WAVEFORM_COLOR))
        
        center_y = self._current_height / 2
        max_bar_height = self._current_height * 0.5
        
        for i, level in enumerate(self._audio_levels):
            bar_height = max(2, level * max_bar_height)
            bar_x = waveform_start + i * (bar_width + bar_spacing)
            if bar_x + bar_width > waveform_end:
                break
            bar_y = center_y - bar_height / 2
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_width, bar_height), 1, 1)
        
        # Draw timer
        painter.setPen(QPen(self.TIMER_COLOR))
        font = QFont("SF Pro", 11)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        
        time_str = self._get_recording_time()
        timer_rect = QRectF(self._current_width - 40, 0, 36, self._current_height)
        painter.drawText(timer_rect, Qt.AlignmentFlag.AlignCenter, time_str)
    
    def _draw_processing(self, painter: QPainter):
        """Draw processing state - similar to recording but orange."""
        # Draw pill background
        path = QPainterPath()
        rect = QRectF(0, 0, self._current_width, self._current_height)
        path.addRoundedRect(rect, self._current_height / 2, self._current_height / 2)
        
        painter.setBrush(QBrush(self.BG_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
        
        # Draw processing icon with orange background (pulsing)
        mic_margin = 4
        mic_size = self._current_height - mic_margin * 2
        mic_x = mic_margin
        mic_y = mic_margin
        
        # Orange circle background with pulse
        color = QColor(self.PROCESSING_COLOR)
        color.setAlphaF(self._pulse_opacity)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QRectF(mic_x, mic_y, mic_size, mic_size))
        
        # Processing dots (animated)
        painter.setBrush(QBrush(self.MIC_ICON_COLOR))
        dot_size = 3
        mic_center_x = mic_x + mic_size / 2
        mic_center_y = mic_y + mic_size / 2
        spacing = 5
        
        for i in range(3):
            dx = (i - 1) * spacing
            painter.drawEllipse(QRectF(
                mic_center_x + dx - dot_size / 2,
                mic_center_y - dot_size / 2,
                dot_size, dot_size
            ))
        
        # Draw shorter text "処理中"
        painter.setPen(QPen(self.TIMER_COLOR))
        font = QFont("Yu Gothic UI", 10)
        painter.setFont(font)
        
        text_rect = QRectF(mic_x + mic_size + 6, 0, self._current_width - mic_size - 14, self._current_height)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "処理中")
    
    def show_indicator(self):
        """Show the overlay."""
        self._position_window()
        self.show()
    
    def hide_indicator(self):
        """Hide the overlay."""
        self.hide()
