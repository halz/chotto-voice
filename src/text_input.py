"""Text input simulation for Chotto Voice."""
import time
import keyboard


class TextInputSimulator:
    """Simulates keyboard input to type text into focused application."""
    
    def __init__(self, typing_delay: float = 0.01):
        """
        Initialize the text input simulator.
        
        Args:
            typing_delay: Delay between characters (seconds)
        """
        self.typing_delay = typing_delay
    
    def type_text(self, text: str, use_clipboard: bool = True):
        """
        Type text into the currently focused text field.
        
        Args:
            text: Text to type
            use_clipboard: If True, use clipboard paste (faster, supports Unicode)
                          If False, simulate individual keystrokes
        """
        if not text:
            return
        
        if use_clipboard:
            self._paste_text(text)
        else:
            self._type_characters(text)
    
    def _paste_text(self, text: str):
        """Paste text using clipboard (faster, better Unicode support)."""
        import pyperclip
        
        # Copy text to clipboard
        pyperclip.copy(text)
        
        # Wait for clipboard to update
        time.sleep(0.1)
        
        # Simulate Ctrl+V
        keyboard.press_and_release('ctrl+v')
        
        # Note: We leave the result in clipboard (useful for re-pasting)
    
    def _type_characters(self, text: str):
        """Type text character by character (slower but more compatible)."""
        for char in text:
            try:
                keyboard.write(char)
                if self.typing_delay > 0:
                    time.sleep(self.typing_delay)
            except Exception:
                # Skip characters that can't be typed
                pass


def type_to_focused_field(text: str, use_clipboard: bool = True):
    """
    Convenience function to type text into the currently focused field.
    
    Args:
        text: Text to type
        use_clipboard: Use clipboard paste method (recommended)
    """
    simulator = TextInputSimulator()
    simulator.type_text(text, use_clipboard)
