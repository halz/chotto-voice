"""Locate the focused text caret / input field across platforms.

Used to float the recording indicator near where the user is actually typing.
This relies on OS accessibility APIs, which are not available for every
application, so every entry point is best-effort: callers must treat ``None``
as "couldn't determine" and fall back to a fixed screen position.

Returns are ``(x, y, width, height)`` rectangles in global (virtual desktop)
screen coordinates.
"""
import sys
from typing import Optional, Tuple

CaretRect = Tuple[int, int, int, int]


def get_caret_rect() -> Optional[CaretRect]:
    """Return the focused caret/field rect, or ``None`` if unavailable."""
    try:
        if sys.platform == "win32":
            return _get_caret_rect_windows()
        if sys.platform == "darwin":
            return _get_caret_rect_macos()
    except Exception:
        # Accessibility calls can fail for sandboxed / elevated apps; never let
        # that take down the caller.
        return None
    return None


# --------------------------------------------------------------------------- #
# Windows — GetGUIThreadInfo gives the caret rect of the foreground thread.
# --------------------------------------------------------------------------- #
def _get_caret_rect_windows() -> Optional[CaretRect]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hwndActive", wintypes.HWND),
            ("hwndFocus", wintypes.HWND),
            ("hwndCapture", wintypes.HWND),
            ("hwndMenuOwner", wintypes.HWND),
            ("hwndMoveSize", wintypes.HWND),
            ("hwndCaret", wintypes.HWND),
            ("rcCaret", RECT),
        ]

    gti = GUITHREADINFO()
    gti.cbSize = ctypes.sizeof(GUITHREADINFO)

    fg_window = user32.GetForegroundWindow()
    if not fg_window:
        return None
    thread_id = user32.GetWindowThreadProcessId(fg_window, None)

    if not user32.GetGUIThreadInfo(thread_id, ctypes.byref(gti)):
        return None

    caret = gti.rcCaret
    width = caret.right - caret.left
    height = caret.bottom - caret.top

    # A caret window with a non-empty rect: convert client coords to screen.
    target_hwnd = gti.hwndCaret or gti.hwndFocus
    if target_hwnd and (width > 0 or height > 0):
        pt = wintypes.POINT(caret.left, caret.top)
        if user32.ClientToScreen(target_hwnd, ctypes.byref(pt)):
            return (pt.x, pt.y, max(width, 1), max(height, 16))

    # No caret rect — fall back to the focused control's window rect.
    if gti.hwndFocus:
        rect = RECT()
        if user32.GetWindowRect(gti.hwndFocus, ctypes.byref(rect)):
            return (
                rect.left,
                rect.top,
                rect.right - rect.left,
                rect.bottom - rect.top,
            )
    return None


# --------------------------------------------------------------------------- #
# macOS — AXUIElement via pyobjc (optional dependency).
# --------------------------------------------------------------------------- #
def _get_caret_rect_macos() -> Optional[CaretRect]:
    try:
        from ApplicationServices import (
            AXUIElementCreateSystemWide,
            AXUIElementCopyAttributeValue,
            AXValueGetValue,
            kAXFocusedUIElementAttribute,
            kAXSelectedTextRangeAttribute,
            kAXBoundsForRangeParameterizedAttribute,
            kAXValueCGRectType,
        )
        from ApplicationServices import AXUIElementCopyParameterizedAttributeValue
        import Quartz
    except Exception:
        # pyobjc not installed → caret following unavailable on macOS.
        return None

    system = AXUIElementCreateSystemWide()

    err, focused = AXUIElementCopyAttributeValue(
        system, kAXFocusedUIElementAttribute, None
    )
    if err != 0 or focused is None:
        return None

    # Get the caret/selection range, then ask for its on-screen bounds.
    err, sel_range = AXUIElementCopyAttributeValue(
        focused, kAXSelectedTextRangeAttribute, None
    )
    if err != 0 or sel_range is None:
        return _macos_element_frame(focused)

    err, bounds_value = AXUIElementCopyParameterizedAttributeValue(
        focused, kAXBoundsForRangeParameterizedAttribute, sel_range, None
    )
    if err != 0 or bounds_value is None:
        return _macos_element_frame(focused)

    ok, rect = AXValueGetValue(bounds_value, kAXValueCGRectType, None)
    if not ok:
        return _macos_element_frame(focused)

    return (
        int(rect.origin.x),
        int(rect.origin.y),
        max(int(rect.size.width), 1),
        max(int(rect.size.height), 16),
    )


def _macos_element_frame(element) -> Optional[CaretRect]:
    """Fallback: the focused element's bounding frame."""
    try:
        from ApplicationServices import (
            AXUIElementCopyAttributeValue,
            AXValueGetValue,
            kAXValueCGPointType,
            kAXValueCGSizeType,
        )
    except Exception:
        return None

    err_p, pos_value = AXUIElementCopyAttributeValue(element, "AXPosition", None)
    err_s, size_value = AXUIElementCopyAttributeValue(element, "AXSize", None)
    if err_p != 0 or err_s != 0 or pos_value is None or size_value is None:
        return None

    ok_p, point = AXValueGetValue(pos_value, kAXValueCGPointType, None)
    ok_s, size = AXValueGetValue(size_value, kAXValueCGSizeType, None)
    if not (ok_p and ok_s):
        return None

    return (int(point.x), int(point.y), int(size.width), int(size.height))
