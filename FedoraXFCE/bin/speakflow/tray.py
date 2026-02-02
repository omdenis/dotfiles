"""System tray icon and menu."""

import pystray
from PIL import Image, ImageDraw
import logging
from config import State, APP_NAME

logger = logging.getLogger(__name__)


class TrayIcon:
    """System tray icon with state visualization."""

    def __init__(self, on_quit):
        """
        Initialize tray icon.

        Args:
            on_quit: Callback function when quit is selected
        """
        self.on_quit = on_quit
        self.icon = None
        self.current_state = State.IDLE

    def create_icon_image(self, state):
        """
        Create icon image based on state.

        Args:
            state: Current application state (IDLE, RECORDING, PROCESSING)

        Returns:
            PIL.Image: Icon image
        """
        # Create a 64x64 image
        size = 64
        image = Image.new('RGB', (size, size), 'white')
        draw = ImageDraw.Draw(image)

        # Choose color based on state
        if state == State.IDLE:
            color = 'gray'
        elif state == State.RECORDING:
            color = 'red'
        elif state == State.PROCESSING:
            color = 'yellow'
        else:
            color = 'gray'

        # Draw filled circle
        margin = 8
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=color,
            outline='black',
            width=2
        )

        return image

    def start(self):
        """Start the system tray icon."""
        try:
            # Create initial icon
            image = self.create_icon_image(State.IDLE)

            # Create menu
            menu = pystray.Menu(
                pystray.MenuItem("SpeakFlow", None, enabled=False),
                pystray.MenuItem("Quit", self._on_quit_clicked)
            )

            # Create and run icon
            self.icon = pystray.Icon(
                APP_NAME,
                image,
                APP_NAME,
                menu
            )

            logger.info("Starting system tray icon")
            self.icon.run()

        except Exception as e:
            logger.error(f"Failed to start tray icon: {e}")

    def update_state(self, state):
        """
        Update icon to reflect new state.

        Args:
            state: New application state
        """
        if self.icon is None:
            return

        self.current_state = state

        try:
            image = self.create_icon_image(state)
            self.icon.icon = image
            logger.info(f"Tray icon updated to state: {state}")
        except Exception as e:
            logger.error(f"Failed to update tray icon: {e}")

    def _on_quit_clicked(self):
        """Handle quit menu item click."""
        logger.info("Quit selected from tray menu")
        if self.icon:
            self.icon.stop()
        if self.on_quit:
            self.on_quit()

    def stop(self):
        """Stop the tray icon."""
        if self.icon:
            self.icon.stop()
