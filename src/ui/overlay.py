"""Overlay indicator for Chotto Voice - shows recording status."""
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen


class OverlayIndicator(QWidget):
    """Small overlay indicator in bottom-right corner."""
    
    def __init__(self, size: int = 24):
        super().__init__()
        self._size = size
        self._state = "idle"  # idle, recording, processing
        self._pulse_opacity = 1.0
        self._pulse_direction = -1
        
        self._setup_window()
        self._setup_animation()
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
        self.setFixedSize(self._size, self._size)
    
    def _setup_animation(self):
        """Setup pulse animation for recording state."""
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._pulse_timer.setInterval(50)  # 20 FPS
    
    def _position_window(self):
        """Position window in bottom-right corner."""
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            x = geometry.right() - self._size - 20  # 20px margin
            y = geometry.bottom() - self._size - 20
            self.move(x, y)
    
    def _update_pulse(self):
        """Update pulse animation."""
        self._pulse_opacity += self._pulse_direction * 0.05
        if self._pulse_opacity <= 0.3:
            self._pulse_opacity = 0.3
            self._pulse_direction = 1
        elif self._pulse_opacity >= 1.0:
            self._pulse_opacity = 1.0
            self._pulse_direction = -1
        self.update()
    
    def set_state(self, state: str):
        """
        Set indicator state.
        
        Args:
            state: "idle", "recording", or "processing"
        """
        self._state = state
        
        if state == "recording":
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
            self._pulse_opacity = 1.0
        
        self.update()
    
    def paintEvent(self, event):
        """Draw the indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Choose color based on state
        if self._state == "recording":
            color = QColor(244, 67, 54)  # Red
            color.setAlphaF(self._pulse_opacity)
        elif self._state == "processing":
            color = QColor(255, 152, 0)  # Orange
        else:  # idle
            color = QColor(76, 175, 80, 100)  # Green, semi-transparent
        
        # Draw circle
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        
        margin = 2
        painter.drawEllipse(margin, margin, 
                           self._size - margin * 2, 
                           self._size - margin * 2)
        
        # Draw inner indicator for recording
        if self._state == "recording":
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            inner_size = self._size // 3
            offset = (self._size - inner_size) // 2
            painter.drawEllipse(offset, offset, inner_size, inner_size)
    
    def show_indicator(self):
        """Show the overlay."""
        self._position_window()  # Reposition in case screen changed
        self.show()
    
    def hide_indicator(self):
        """Hide the overlay."""
        self.hide()
