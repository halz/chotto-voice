"""Text input simulation for Chotto Voice.

Types recognised / formatted text into whatever application currently has
keyboard focus. Uses clipboard-paste by default because it is fast and handles
Unicode (Japanese) reliably, and it picks the correct paste shortcut per
platform (``cmd+v`` on macOS, ``ctrl+v`` elsewhere — the previous code was
hard-coded to ``ctrl+v`` and silently failed on macOS).

``StreamingTyper`` supports writing the AI-formatted text into the field
incrementally as it streams in, instead of waiting for the whole result.
"""
import sys
import time

import keyboard

# macOS pastes with Command+V; Windows / Linux use Control+V.
PASTE_HOTKEY = "command+v" if sys.platform == "darwin" else "ctrl+v"


def _get_clipboard() -> str:
    try:
        import pyperclip

        return pyperclip.paste()
    except Exception:
        return ""


def _set_clipboard(text: str) -> bool:
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception:
        return False


class TextInputSimulator:
    """Simulates keyboard input to type text into the focused application."""

    def __init__(self, typing_delay: float = 0.01):
        self.typing_delay = typing_delay

    def type_text(self, text: str, use_clipboard: bool = True):
        """Type ``text`` into the currently focused text field."""
        if not text:
            return
        if use_clipboard:
            self._paste_text(text)
        else:
            self._type_characters(text)

    def _paste_text(self, text: str, settle: float = 0.08):
        """Paste text via the clipboard (fast, good Unicode support)."""
        if not _set_clipboard(text):
            # Clipboard unavailable — fall back to per-character typing.
            self._type_characters(text)
            return
        time.sleep(settle)
        keyboard.press_and_release(PASTE_HOTKEY)

    def _type_characters(self, text: str):
        """Type text character by character (slower but more compatible)."""
        for char in text:
            try:
                keyboard.write(char)
                if self.typing_delay > 0:
                    time.sleep(self.typing_delay)
            except Exception:
                pass  # Skip characters that can't be typed.


class StreamingTyper:
    """Types streamed text into the focused field one segment at a time.

    Chunks are buffered and flushed at natural boundaries (spaces, punctuation)
    or once the buffer grows past ``max_buffer`` characters, so the field
    updates roughly word-by-word as the AI response streams in. The user's
    existing clipboard contents are saved on ``start`` and restored on
    ``finish`` so streaming is non-destructive.
    """

    BOUNDARY_CHARS = set(" \n\t、。，．！？!?,.;:　")

    def __init__(self, simulator: "TextInputSimulator | None" = None, max_buffer: int = 16):
        self.sim = simulator or TextInputSimulator()
        self.max_buffer = max_buffer
        self._buffer = ""
        self._saved_clipboard = ""
        self._active = False

    def start(self):
        self._buffer = ""
        self._saved_clipboard = _get_clipboard()
        self._active = True

    def feed(self, chunk: str):
        """Add a streamed chunk, flushing any complete leading segment."""
        if not self._active:
            self.start()
        self._buffer += chunk

        # Flush everything up to and including the last boundary character so we
        # emit whole words rather than partial tokens.
        last_boundary = -1
        for i, ch in enumerate(self._buffer):
            if ch in self.BOUNDARY_CHARS:
                last_boundary = i

        if last_boundary >= 0:
            to_emit = self._buffer[: last_boundary + 1]
            self._buffer = self._buffer[last_boundary + 1:]
            self._emit(to_emit)
        elif len(self._buffer) >= self.max_buffer:
            self._emit(self._buffer)
            self._buffer = ""

    def finish(self):
        """Flush any remaining buffered text and restore the clipboard."""
        if self._buffer:
            self._emit(self._buffer)
            self._buffer = ""
        if self._active and self._saved_clipboard:
            # Give the last paste time to land before restoring the clipboard.
            time.sleep(0.1)
            _set_clipboard(self._saved_clipboard)
        self._active = False

    def _emit(self, text: str):
        if text:
            self.sim._paste_text(text, settle=0.03)


def type_to_focused_field(text: str, use_clipboard: bool = True):
    """Convenience helper to type text into the currently focused field."""
    TextInputSimulator().type_text(text, use_clipboard)
