"""Text insertion into active application."""

import pyperclip
from pynput.keyboard import Controller, Key
import time
import logging

logger = logging.getLogger(__name__)


class TextPaster:
    """Handles pasting transcribed text into active application."""

    def __init__(self):
        self.keyboard = Controller()

    def paste_text(self, text, restore_clipboard=False):
        """
        Paste text into the active application.

        Args:
            text: Text to paste
            restore_clipboard: Whether to restore original clipboard contents

        Returns:
            bool: True if successful
        """
        if not text:
            logger.warning("No text to paste")
            return False

        try:
            # Save original clipboard if requested
            original_clipboard = None
            if restore_clipboard:
                try:
                    original_clipboard = pyperclip.paste()
                except:
                    pass

            # Copy text to clipboard
            pyperclip.copy(text)
            logger.info("Text copied to clipboard")

            # Small delay to ensure clipboard is ready
            time.sleep(0.1)

            # Simulate Ctrl+V to paste
            with self.keyboard.pressed(Key.ctrl):
                self.keyboard.press('v')
                self.keyboard.release('v')

            logger.info("Text pasted via Ctrl+V")

            # Restore original clipboard if requested
            if restore_clipboard and original_clipboard is not None:
                time.sleep(0.2)  # Wait for paste to complete
                try:
                    pyperclip.copy(original_clipboard)
                except:
                    pass

            return True

        except Exception as e:
            logger.error(f"Failed to paste text: {e}")
            return False
