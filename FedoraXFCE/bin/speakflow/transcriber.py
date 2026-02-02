"""Whisper integration for speech-to-text."""

import whisper
import logging
from pathlib import Path
from config import WHISPER_MODEL, WHISPER_LANGUAGE

logger = logging.getLogger(__name__)


class Transcriber:
    """Handles speech-to-text transcription using OpenAI Whisper."""

    def __init__(self, model_name=WHISPER_MODEL):
        self.model_name = model_name
        self.model = None

    def load_model(self):
        """Load the Whisper model (one-time operation)."""
        if self.model is not None:
            return True

        try:
            logger.info(f"Loading Whisper model: {self.model_name}")
            self.model = whisper.load_model(self.model_name)
            logger.info("Whisper model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False

    def transcribe(self, audio_file):
        """Transcribe audio file to text."""
        if self.model is None:
            logger.error("Model not loaded")
            return None

        if not Path(audio_file).exists():
            logger.error(f"Audio file not found: {audio_file}")
            return None

        try:
            logger.info(f"Transcribing audio file: {audio_file}")

            # Transcribe with Whisper
            result = self.model.transcribe(
                str(audio_file),
                language=WHISPER_LANGUAGE,
                fp16=False  # Disable FP16 for CPU compatibility
            )

            text = result["text"].strip()
            logger.info(f"Transcription complete: {text[:50]}...")

            return text

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None
