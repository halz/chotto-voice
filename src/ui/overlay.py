"""Overlay indicator for Chotto Voice - iOS-style recording indicator."""
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPainterPath
import time
import random


class OverlayIndicator(QWidget):
    """iOS-style overlay indicator in bottom-right corner."""
    
    # Sizes
    IDLE_WIDTH = 60
    IDLE_HEIGHT = 30
    RECORDING_WIDTH = 280
    RECORDING_HEIGHT = 44
    
    # Colors
    BG_COLOR = QColor(45, 45, 48, 230)  # Dark gray, slightly transparent
    IDLE_DOT_COLOR = QColor(100, 100, 120)  # Muted blue-gray
    MIC_BG_COLOR = QColor(220, 50, 47)  # Red
    MIC_ICON_COLOR = QColor(255, 255, 255)  # White
    WAVEFORM_COLOR = QColor(180, 180, 180)  # Light gray
    TIMER_COLOR = QColor(160, 160, 160)  # Gray
    PROCESSING_COLOR = QColor(255, 152, 0)  # Orange
    
    def __init__(self, size: int = 24):
        super().__init__()
        self._state = "idle"  # idle, recording, processing
        self._recording_start_time = 0
        self._audio_levels = [0.1] * 40  # Waveform data
        self._current_width = self.IDLE_WIDTH
        self._current_height = self.IDLE_HEIGHT
        self._pulse_opacity = 1.0
        self._pulse_direction = -1
        
        self._setup_window()
        self._setup_timers()
        self._position_window()
    
    def _setup_window(self):
        """Configure window properties."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |  # Don't show in taskbar
            Qt.WindowType.WindowTransparentForInput  # Click-through
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._update_size()
    
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
    
    def _update_size(self):
        """Update widget size based on state."""
        if self._state == "idle":
            self._current_width = self.IDLE_WIDTH
            self._current_height = self.IDLE_HEIGHT
        else:
            self._current_width = self.RECORDING_WIDTH
            self._current_height = self.RECORDING_HEIGHT
        
        self.setFixedSize(self._current_width, self._current_height)
        self._position_window()
    
    def _position_window(self):
        """Position window in bottom-right corner."""
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            x = geometry.right() - self._current_width - 20  # 20px margin
            y = geometry.bottom() - self._current_height - 20
            self.move(x, y)
    
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
        if self._state == state:
            return
        
        self._state = state
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
        dot_size = 8
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
        mic_margin = 6
        mic_size = self._current_height - mic_margin * 2
        mic_x = mic_margin
        mic_y = mic_margin
        
        # Red circle background
        painter.setBrush(QBrush(self.MIC_BG_COLOR))
        painter.drawEllipse(QRectF(mic_x, mic_y, mic_size, mic_size))
        
        # Microphone icon (simplified)
        painter.setPen(QPen(self.MIC_ICON_COLOR, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        mic_center_x = mic_x + mic_size / 2
        mic_center_y = mic_y + mic_size / 2
        
        # Mic body (rounded rectangle)
        mic_body_w = mic_size * 0.3
        mic_body_h = mic_size * 0.45
        mic_body_rect = QRectF(
            mic_center_x - mic_body_w / 2,
            mic_center_y - mic_body_h / 2 - 2,
            mic_body_w,
            mic_body_h
        )
        painter.drawRoundedRect(mic_body_rect, mic_body_w / 2, mic_body_w / 2)
        
        # Mic stand arc
        arc_rect = QRectF(
            mic_center_x - mic_size * 0.25,
            mic_center_y - mic_size * 0.15,
            mic_size * 0.5,
            mic_size * 0.4
        )
        painter.drawArc(arc_rect, 0, -180 * 16)
        
        # Mic stand line
        painter.drawLine(
            QPointF(mic_center_x, mic_center_y + mic_size * 0.25),
            QPointF(mic_center_x, mic_center_y + mic_size * 0.35)
        )
        
        # Draw waveform
        waveform_start = mic_x + mic_size + 12
        waveform_end = self._current_width - 55
        waveform_width = waveform_end - waveform_start
        bar_count = len(self._audio_levels)
        bar_width = 2
        bar_spacing = (waveform_width - bar_count * bar_width) / (bar_count - 1)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.WAVEFORM_COLOR))
        
        center_y = self._current_height / 2
        max_bar_height = self._current_height * 0.5
        
        for i, level in enumerate(self._audio_levels):
            bar_height = max(2, level * max_bar_height)
            bar_x = waveform_start + i * (bar_width + bar_spacing)
            bar_y = center_y - bar_height / 2
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_width, bar_height), 1, 1)
        
        # Draw timer
        painter.setPen(QPen(self.TIMER_COLOR))
        font = QFont("SF Pro", 13)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        
        time_str = self._get_recording_time()
        timer_rect = QRectF(self._current_width - 50, 0, 45, self._current_height)
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
        mic_margin = 6
        mic_size = self._current_height - mic_margin * 2
        mic_x = mic_margin
        mic_y = mic_margin
        
        # Orange circle background with pulse
        color = QColor(self.PROCESSING_COLOR)
        color.setAlphaF(self._pulse_opacity)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QRectF(mic_x, mic_y, mic_size, mic_size))
        
        # Processing dots
        painter.setBrush(QBrush(self.MIC_ICON_COLOR))
        dot_size = 4
        mic_center_x = mic_x + mic_size / 2
        mic_center_y = mic_y + mic_size / 2
        spacing = 6
        
        for i in range(3):
            dx = (i - 1) * spacing
            painter.drawEllipse(QRectF(
                mic_center_x + dx - dot_size / 2,
                mic_center_y - dot_size / 2,
                dot_size, dot_size
            ))
        
        # Draw "処理中..." text
        painter.setPen(QPen(self.TIMER_COLOR))
        font = QFont("SF Pro", 13)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        
        text_rect = QRectF(mic_x + mic_size + 10, 0, self._current_width - mic_size - 30, self._current_height)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "処理中...")
    
    def show_indicator(self):
        """Show the overlay."""
        self._position_window()
        self.show()
    
    def hide_indicator(self):
        """Hide the overlay."""
        self.hide()
