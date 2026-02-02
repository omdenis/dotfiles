"""Global hotkey detection."""

from pynput import keyboard
import logging

logger = logging.getLogger(__name__)


class HotkeyListener:
    """Listens for global hotkey combination."""

    def __init__(self, callback):
        """
        Initialize hotkey listener.

        Args:
            callback: Function to call when hotkey is pressed
        """
        self.callback = callback
        self.listener = None

    def start(self):
        """Start listening for the hotkey."""
        try:
            # Use GlobalHotKeys for Ctrl+Space
            self.listener = keyboard.GlobalHotKeys({
                '<ctrl>+<space>': self.callback
            })
            self.listener.start()
            logger.info("Hotkey listener started (Ctrl+Space)")
            return True
        except Exception as e:
            logger.error(f"Failed to start hotkey listener: {e}")
            return False

    def stop(self):
        """Stop listening for the hotkey."""
        if self.listener:
            self.listener.stop()
            logger.info("Hotkey listener stopped")
