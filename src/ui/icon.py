"""Generate application icon for system tray."""
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QBrush, QPen
from PyQt6.QtCore import Qt, QRect


def create_tray_icon(size: int = 32) -> QIcon:
    """Create a simple tray icon."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))  # Transparent
    
    painter = QPainter()
    if painter.begin(pixmap):
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            
            # Draw green circle
            painter.setBrush(QBrush(QColor(76, 175, 80)))
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawEllipse(1, 1, size - 2, size - 2)
            
            # Draw "V" letter
            painter.setPen(QPen(QColor(255, 255, 255)))
            font = QFont("Arial", int(size * 0.45), QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "V")
        finally:
            painter.end()
    
    return QIcon(pixmap)


def create_recording_icon(size: int = 32) -> QIcon:
    """Create icon for recording state."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    
    painter = QPainter()
    if painter.begin(pixmap):
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            
            # Draw red circle
            painter.setBrush(QBrush(QColor(244, 67, 54)))
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawEllipse(1, 1, size - 2, size - 2)
            
            # Draw white inner circle
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            inner = size // 3
            offset = (size - inner) // 2
            painter.drawEllipse(offset, offset, inner, inner)
        finally:
            painter.end()
    
    return QIcon(pixmap)


def create_processing_icon(size: int = 32) -> QIcon:
    """Create icon for processing state."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    
    painter = QPainter()
    if painter.begin(pixmap):
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            
            # Draw orange circle
            painter.setBrush(QBrush(QColor(255, 152, 0)))
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawEllipse(1, 1, size - 2, size - 2)
            
            # Draw "..." text
            painter.setPen(QPen(QColor(255, 255, 255)))
            font = QFont("Arial", int(size * 0.35), QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "•••")
        finally:
            painter.end()
    
    return QIcon(pixmap)
