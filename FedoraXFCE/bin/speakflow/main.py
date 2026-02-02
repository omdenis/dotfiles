#!/usr/bin/env python3
"""
SpeakFlow - Voice-to-Text Application
Main orchestrator for the application.
"""

import logging
import sys
import threading
from pathlib import Path

from config import State, APP_NAME
from recorder import AudioRecorder
from transcriber import Transcriber
from hotkey import HotkeyListener
from paster import TextPaster
from tray import TrayIcon

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SpeakFlow:
    """Main application orchestrator."""

    def __init__(self):
        self.state = State.IDLE
        self.state_lock = threading.Lock()

        # Initialize components
        self.recorder = AudioRecorder()
        self.transcriber = Transcriber()
        self.paster = TextPaster()
        self.hotkey_listener = HotkeyListener(self.on_hotkey_pressed)
        self.tray = TrayIcon(self.quit)

        self.running = True

    def on_hotkey_pressed(self):
        """Callback when Ctrl+Space is pressed."""
        with self.state_lock:
            if self.state == State.IDLE:
                self._start_recording()
            elif self.state == State.RECORDING:
                self._stop_recording_and_process()
            else:
                logger.warning(f"Hotkey pressed during {self.state} state, ignoring")

    def _start_recording(self):
        """Start recording audio."""
        logger.info("Starting recording")
        self.state = State.RECORDING
        self.tray.update_state(State.RECORDING)

        if not self.recorder.start_recording():
            logger.error("Failed to start recording")
            self.state = State.IDLE
            self.tray.update_state(State.IDLE)

    def _stop_recording_and_process(self):
        """Stop recording and process the audio in a background thread."""
        logger.info("Stopping recording")
        self.state = State.PROCESSING
        self.tray.update_state(State.PROCESSING)

        # Process in background thread to avoid blocking
        thread = threading.Thread(target=self._process_audio)
        thread.daemon = True
        thread.start()

    def _process_audio(self):
        """Process recorded audio (runs in background thread)."""
        try:
            # Stop recording and get audio file
            audio_file = self.recorder.stop_recording()

            if audio_file is None:
                logger.error("No audio file to process")
                with self.state_lock:
                    self.state = State.IDLE
                    self.tray.update_state(State.IDLE)
                return

            # Transcribe audio
            text = self.transcriber.transcribe(audio_file)

            if text is None or not text.strip():
                logger.warning("No text transcribed")
                with self.state_lock:
                    self.state = State.IDLE
                    self.tray.update_state(State.IDLE)
                return

            # Paste text into active application
            logger.info(f"Transcribed text: {text}")
            self.paster.paste_text(text, restore_clipboard=False)

            # Return to idle state
            with self.state_lock:
                self.state = State.IDLE
                self.tray.update_state(State.IDLE)

            logger.info("Processing complete")

        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            with self.state_lock:
                self.state = State.IDLE
                self.tray.update_state(State.IDLE)

    def start(self):
        """Start the application."""
        logger.info(f"Starting {APP_NAME}")

        # Load Whisper model
        logger.info("Loading Whisper model (this may take a moment)...")
        if not self.transcriber.load_model():
            logger.error("Failed to load Whisper model, exiting")
            return False

        # Start hotkey listener
        if not self.hotkey_listener.start():
            logger.error("Failed to start hotkey listener, exiting")
            return False

        logger.info(f"{APP_NAME} started successfully")
        logger.info("Press Ctrl+Space to start/stop recording")

        # Start tray icon (this blocks until quit)
        self.tray.start()

        return True

    def quit(self):
        """Quit the application."""
        logger.info(f"Shutting down {APP_NAME}")
        self.running = False

        # Stop components
        self.hotkey_listener.stop()

        # If recording, stop it
        if self.state == State.RECORDING:
            self.recorder.stop_recording()

        self.tray.stop()

        logger.info("Shutdown complete")
        sys.exit(0)


def main():
    """Main entry point."""
    app = SpeakFlow()

    try:
        app.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        app.quit()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
