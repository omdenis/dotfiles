#!/usr/bin/env python3
"""
Simple voice-to-text tool for Obsidian inbox.
Press Enter to start/stop recording. Transcribes with Whisper turbo, appends to inbox.md
"""

import subprocess
import tempfile
import os
import sys
import time
import select
import termios
import tty
import warnings

# Audio recording settings
SAMPLE_RATE = 16000
CHANNELS = 1
INBOX_FILE = "/home/denis/Documents/PersonalSync/notes/tt/inbox.md"


def record_audio(output_path):
    """Record audio from microphone. Returns success boolean."""
    try:
        import sounddevice as sd
        import numpy as np
        from scipy.io import wavfile
    except ImportError:
        print("pip install sounddevice numpy scipy")
        sys.exit(1)

    recording = []
    stop_recording = False
    last_dot_time = time.time()

    def audio_callback(indata, frames, time_info, status):
        recording.append(indata.copy())

    old_settings = termios.tcgetattr(sys.stdin)

    try:
        tty.setcbreak(sys.stdin.fileno())
        print("Recording (press Enter to stop)...")

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=audio_callback):
            sys.stdout.write(".")
            sys.stdout.flush()
            last_dot_time = time.time()

            while not stop_recording:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1)
                    if key == "\n" or key == "\r":
                        stop_recording = True
                else:
                    if time.time() - last_dot_time >= 0.5:
                        sys.stdout.write(".")
                        sys.stdout.flush()
                        last_dot_time = time.time()

        print()

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    if not recording:
        return False

    audio_data = np.concatenate(recording, axis=0)
    audio_int16 = (audio_data * 32767).astype(np.int16)
    wavfile.write(output_path, SAMPLE_RATE, audio_int16)

    return True


def load_whisper_model():
    """Load Whisper turbo model."""
    try:
        import whisper
    except ImportError:
        print("pip install openai-whisper")
        sys.exit(1)

    warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")
    return whisper.load_model("turbo")


def transcribe_audio(audio_path, model):
    """Transcribe audio using Whisper."""
    result = model.transcribe(audio_path, language="ru")
    return result["text"].strip()


def append_to_inbox(text):
    """Append text to inbox file with blank line separator."""
    os.makedirs(os.path.dirname(INBOX_FILE), exist_ok=True)
    
    with open(INBOX_FILE, "a", encoding="utf-8") as f:
        f.write("\n\n" + text)
    
    print(f"✓ Appended to {INBOX_FILE}")


def main():
    # Relaunch in terminal if not running in one
    if not sys.stdin.isatty():
        script = os.path.abspath(__file__)
        cmd = [
            "xfce4-terminal",
            "--geometry=60x8",
            "--hide-menubar",
            "--hide-toolbar",
            "--hide-scrollbar",
            "--title=Voice to Obsidian",
            "-x", "python3", script
        ]
        subprocess.run(cmd)
        return 0

    print("Loading turbo model...")
    whisper_model = load_whisper_model()
    print("Ready! Press Enter to start recording.\n")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        audio_path = tmp_file.name

    try:
        while True:
            # Wait for Enter to start recording
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setcbreak(sys.stdin.fileno())
                while True:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1)
                        if key == "\n" or key == "\r":
                            break
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

            # Record audio
            success = record_audio(audio_path)
            if not success:
                continue

            # Transcribe
            print("Transcribing", end="", flush=True)
            start_time = time.time()
            
            text = transcribe_audio(audio_path, whisper_model)
            elapsed = time.time() - start_time
            print(f" ({elapsed:.1f}s)")

            if not text:
                print("No speech detected.\n")
                continue

            # Show and save
            print(f"\n{text}\n")
            append_to_inbox(text)
            print()

    except KeyboardInterrupt:
        print("\nBye!")
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
