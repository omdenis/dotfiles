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

# Audio recording settings
SAMPLE_RATE = 16000
CHANNELS = 1


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


def record_audio(output_path, duration=None):
    """
    Record audio from microphone.
    If duration is None, records until Enter is pressed.
    """
    try:
        import sounddevice as sd
        import numpy as np
        from scipy.io import wavfile
    except ImportError:
        print("Error: Required packages not installed.")
        print("Run: pip install sounddevice numpy scipy")
        sys.exit(1)

    print("Recording... Press Enter to stop." if duration is None else f"Recording for {duration} seconds...")

    if duration is None:
        # Record until Enter is pressed
        recording = []

        def callback(indata, frames, time_info, status):
            recording.append(indata.copy())

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
            input()  # Wait for Enter

        if recording:
            audio_data = np.concatenate(recording, axis=0)
        else:
            print("No audio recorded.")
            return False
    else:
        # Record for specified duration
        audio_data = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.float32
        )
        sd.wait()

    # Convert to int16 for WAV file
    audio_int16 = (audio_data * 32767).astype(np.int16)
    wavfile.write(output_path, SAMPLE_RATE, audio_int16)

    print("Recording stopped.")
    return True


def transcribe_audio(audio_path, model_name="base"):
    """Transcribe audio using Whisper."""
    try:
        import whisper
    except ImportError:
        print("Error: whisper not installed.")
        print("Run: pip install openai-whisper")
        sys.exit(1)

    print(f"Transcribing with Whisper ({model_name} model)...")
    model = whisper.load_model(model_name)
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
        "-d", "--duration",
        type=float,
        default=None,
        help="Recording duration in seconds (default: record until Enter)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model to use (default: base)"
    )
    parser.add_argument(
        "--no-paste",
        action="store_true",
        help="Only copy to clipboard, don't paste"
    )
    args = parser.parse_args()

    # Save current active window
    original_window = get_active_window()
    print(f"Active window saved: {original_window}")

    # Record audio to temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        audio_path = tmp_file.name

    try:
        if not record_audio(audio_path, args.duration):
            return 1

        # Transcribe audio
        text = transcribe_audio(audio_path, args.model)

        if not text:
            print("No speech detected.")
            return 1

        print(f"Transcribed: {text}")

        # Copy to clipboard
        if not copy_to_clipboard(text):
            return 1

        if not args.no_paste:
            # Return focus to original window and paste
            focus_window(original_window)
            time.sleep(0.1)
            paste_from_clipboard()
            print("Text pasted.")
        else:
            print("Text copied to clipboard.")

    finally:
        # Clean up temporary file
        if os.path.exists(audio_path):
            os.remove(audio_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
