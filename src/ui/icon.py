"""Generate application icon for system tray."""
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt


def create_tray_icon(text: str = "🎤", size: int = 64) -> QIcon:
    """
    Create a simple tray icon with emoji or text.
    
    Args:
        text: Emoji or text to display
        size: Icon size in pixels
    
    Returns:
        QIcon object
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw background circle
    painter.setBrush(QColor(76, 175, 80))  # Green
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)
    
    # Draw text/emoji
    painter.setPen(QColor(255, 255, 255))
    font = QFont()
    font.setPointSize(int(size * 0.5))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "V")
    
    painter.end()
    
    return QIcon(pixmap)


def create_recording_icon(size: int = 64) -> QIcon:
    """Create icon for recording state."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw red circle
    painter.setBrush(QColor(244, 67, 54))  # Red
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)
    
    # Draw inner circle (recording indicator)
    painter.setBrush(QColor(255, 255, 255))
    inner_size = size // 3
    offset = (size - inner_size) // 2
    painter.drawEllipse(offset, offset, inner_size, inner_size)
    
    painter.end()
    
    return QIcon(pixmap)


def create_processing_icon(size: int = 64) -> QIcon:
    """Create icon for processing state."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw orange circle
    painter.setBrush(QColor(255, 152, 0))  # Orange
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)
    
    # Draw text
    painter.setPen(QColor(255, 255, 255))
    font = QFont()
    font.setPointSize(int(size * 0.4))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "...")
    
    painter.end()
    
    return QIcon(pixmap)
