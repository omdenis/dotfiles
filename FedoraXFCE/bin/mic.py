#!/usr/bin/env python3
"""
Voice-to-text input tool.
Records audio from microphone, transcribes with Whisper, and pastes into active window.
"""

import subprocess
import tempfile
import os
import sys
import time
import argparse
import select
import termios
import tty

# Audio recording settings
SAMPLE_RATE = 16000
CHANNELS = 1

# Language mapping
LANGUAGES = {
    "1": ("en", "English"),
    "2": ("ru", "Russian"),
    "3": ("da", "Danish"),
}


def get_active_window():
    """Get the currently active window ID using xdotool."""
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def focus_window(window_id):
    """Focus on a specific window."""
    if window_id:
        subprocess.run(["xdotool", "windowactivate", window_id], check=False)
        time.sleep(0.1)


def print_recording_help():
    """Print help message during recording."""
    print("\n" + "=" * 50)
    print("RECORDING... Press Enter to stop")
    print("=" * 50)
    print("Language selection (press during recording):")
    print("  1 - English")
    print("  2 - Russian")
    print("  3 - Danish")
    print("  (default: auto-detect)")
    print("=" * 50 + "\n")


def record_audio(output_path, duration=None):
    """
    Record audio from microphone.
    Returns (success, language_code).
    """
    try:
        import sounddevice as sd
        import numpy as np
        from scipy.io import wavfile
    except ImportError:
        print("Error: Required packages not installed.")
        print("Run: pip install sounddevice numpy scipy")
        sys.exit(1)

    language = None
    recording = []
    stop_recording = False

    def audio_callback(indata, frames, time_info, status):
        recording.append(indata.copy())

    # Setup terminal for non-blocking input
    old_settings = termios.tcgetattr(sys.stdin)

    try:
        tty.setcbreak(sys.stdin.fileno())
        print_recording_help()

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=audio_callback):
            while not stop_recording:
                # Check for keyboard input (non-blocking)
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1)
                    if key == "\n" or key == "\r":
                        stop_recording = True
                    elif key in LANGUAGES:
                        lang_code, lang_name = LANGUAGES[key]
                        language = lang_code
                        print(f"\r>> Language set: {lang_name}          ")

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    if recording:
        audio_data = np.concatenate(recording, axis=0)
    else:
        print("No audio recorded.")
        return False, None

    # Convert to int16 for WAV file
    audio_int16 = (audio_data * 32767).astype(np.int16)
    wavfile.write(output_path, SAMPLE_RATE, audio_int16)

    print("\nRecording stopped.")
    return True, language


def transcribe_audio(audio_path, model_name="turbo", language=None):
    """Transcribe audio using Whisper."""
    try:
        import whisper
    except ImportError:
        print("Error: whisper not installed.")
        print("Run: pip install openai-whisper")
        sys.exit(1)

    lang_str = language if language else "auto-detect"
    print(f"Transcribing with Whisper ({model_name} model, language: {lang_str})...")

    model = whisper.load_model(model_name)

    if language:
        result = model.transcribe(audio_path, language=language)
    else:
        result = model.transcribe(audio_path)

    return result["text"].strip()


def copy_to_clipboard(text):
    """Copy text to clipboard using xclip."""
    try:
        process = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE
        )
        process.communicate(input=text.encode("utf-8"))
        return True
    except FileNotFoundError:
        print("Error: xclip not found. Install with: sudo dnf install xclip")
        return False


def paste_from_clipboard():
    """Paste from clipboard using xdotool."""
    subprocess.run(["xdotool", "key", "ctrl+v"], check=False)


def main():
    parser = argparse.ArgumentParser(description="Voice-to-text input tool")
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="turbo",
        choices=["tiny", "base", "small", "medium", "large", "turbo"],
        help="Whisper model to use (default: turbo)"
    )
    parser.add_argument(
        "-l", "--language",
        type=str,
        default=None,
        choices=["en", "ru", "da"],
        help="Force language (default: auto-detect)"
    )
    parser.add_argument(
        "--no-paste",
        action="store_true",
        help="Only copy to clipboard, don't paste"
    )
    args = parser.parse_args()

    # Save current active window
    original_window = get_active_window()

    # Record audio to temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        audio_path = tmp_file.name

    try:
        success, language = record_audio(audio_path)
        if not success:
            return 1

        # Command line language overrides interactive selection
        if args.language:
            language = args.language

        # Transcribe audio
        text = transcribe_audio(audio_path, args.model, language)

        if not text:
            print("No speech detected.")
            return 1

        # Copy to clipboard
        if not copy_to_clipboard(text):
            return 1

        print("\n" + "=" * 50)
        print("TRANSCRIBED TEXT:")
        print("=" * 50)
        print(text)
        print("=" * 50)
        print("Copied to clipboard. Closing in 3 seconds...")
        time.sleep(3)

    finally:
        # Clean up temporary file
        if os.path.exists(audio_path):
            os.remove(audio_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
