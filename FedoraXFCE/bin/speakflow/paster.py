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

    def paste_text(self, text, restore_clipboard=False, use_fallback=True, prefer_typing=False):
        """
        Paste text into the active application.

        Args:
            text: Text to paste
            restore_clipboard: Whether to restore original clipboard contents
            use_fallback: Whether to use direct typing if clipboard paste fails
            prefer_typing: If True, use direct typing instead of clipboard

        Returns:
            bool: True if successful
        """
        if not text:
            logger.warning("No text to paste")
            return False

        # If direct typing is preferred, use it immediately
        if prefer_typing:
            logger.info("Using direct typing (preferred mode)")
            return self._type_directly(text)

        # Try clipboard method first
        success = self._paste_via_clipboard(text, restore_clipboard)

        if not success and use_fallback:
            logger.info("Clipboard paste failed, falling back to direct typing")
            success = self._type_directly(text)

        return success

    def _paste_via_clipboard(self, text, restore_clipboard=False):
        """
        Paste text using clipboard + Ctrl+V.

        Args:
            text: Text to paste
            restore_clipboard: Whether to restore original clipboard contents

        Returns:
            bool: True if successful
        """
        try:
            # Save original clipboard if requested
            original_clipboard = None
            if restore_clipboard:
                try:
                    original_clipboard = pyperclip.paste()
                except:
                    pass

            # Clear clipboard first to avoid interference
            try:
                pyperclip.copy('')
                time.sleep(0.05)
            except:
                pass

            # Copy text to clipboard
            pyperclip.copy(text)
            logger.info("Text copied to clipboard")

            # Longer delay for clipboard to settle
            time.sleep(0.15)

            # Verify clipboard content
            try:
                clipboard_content = pyperclip.paste()
                if clipboard_content != text:
                    logger.warning("Clipboard verification failed")
                    return False
            except:
                logger.warning("Could not verify clipboard content")

            # Simulate Ctrl+V to paste
            with self.keyboard.pressed(Key.ctrl):
                self.keyboard.press('v')
                self.keyboard.release('v')

            logger.info("Text pasted via Ctrl+V")

            # Wait for paste to complete
            time.sleep(0.1)

            # Restore original clipboard if requested
            if restore_clipboard and original_clipboard is not None:
                time.sleep(0.1)
                try:
                    pyperclip.copy(original_clipboard)
                except:
                    pass

            return True

        except Exception as e:
            logger.error(f"Failed to paste via clipboard: {e}")
            return False

    def _type_directly(self, text):
        """
        Type text character by character (fallback method).

        Args:
            text: Text to type

        Returns:
            bool: True if successful
        """
        try:
            logger.info("Typing text directly")

            # Type each character
            for char in text:
                self.keyboard.type(char)
                # Small delay between characters for stability
                time.sleep(0.01)

            logger.info("Text typed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to type text directly: {e}")
            return False
