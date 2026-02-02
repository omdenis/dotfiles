"""Configuration management for SpeakFlow."""

import os
from pathlib import Path

# Application settings
APP_NAME = "SpeakFlow"
SAMPLE_RATE = 16000  # Optimal for Whisper
CHANNELS = 1  # Mono audio

# Whisper settings
WHISPER_MODEL = "base"  # Options: tiny, base, small, medium, large
WHISPER_LANGUAGE = None  # None for auto-detect, or set to "en", "es", etc.

# Hotkey settings
HOTKEY = "<ctrl>+<space>"

# Pasting settings
PREFER_DIRECT_TYPING = False  # If True, always use direct typing (slower but more compatible)
USE_TYPING_FALLBACK = True    # Fall back to direct typing if clipboard paste fails
RESTORE_CLIPBOARD = False     # Restore original clipboard after pasting

# Temporary file settings
TEMP_DIR = Path("/tmp") / "speakflow"
TEMP_DIR.mkdir(exist_ok=True)
TEMP_AUDIO_FILE = TEMP_DIR / "recording.wav"

# Application state
class State:
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
