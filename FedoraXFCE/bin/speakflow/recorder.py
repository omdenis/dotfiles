"""Audio recording functionality."""

import sounddevice as sd
import scipy.io.wavfile as wavfile
import numpy as np
from pathlib import Path
import logging
from config import SAMPLE_RATE, CHANNELS, TEMP_AUDIO_FILE

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Handles audio recording to WAV file."""

    def __init__(self):
        self.recording = []
        self.is_recording = False
        self.stream = None

    def start_recording(self):
        """Start recording audio from the default microphone."""
        if self.is_recording:
            logger.warning("Already recording")
            return False

        self.recording = []
        self.is_recording = True

        try:
            # Start recording in a callback mode
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                callback=self._audio_callback
            )
            self.stream.start()
            logger.info("Recording started")
            return True
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.is_recording = False
            return False

    def _audio_callback(self, indata, frames, time, status):
        """Callback function for audio stream."""
        if status:
            logger.warning(f"Audio callback status: {status}")
        if self.is_recording:
            self.recording.append(indata.copy())

    def stop_recording(self):
        """Stop recording and save to WAV file."""
        if not self.is_recording:
            logger.warning("Not currently recording")
            return None

        self.is_recording = False

        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None

            if not self.recording:
                logger.warning("No audio data recorded")
                return None

            # Concatenate all recorded chunks
            audio_data = np.concatenate(self.recording, axis=0)

            # Save to WAV file
            wavfile.write(TEMP_AUDIO_FILE, SAMPLE_RATE, audio_data)
            logger.info(f"Recording saved to {TEMP_AUDIO_FILE}")

            return TEMP_AUDIO_FILE

        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
            return None
