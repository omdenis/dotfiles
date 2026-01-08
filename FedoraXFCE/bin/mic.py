#!/usr/bin/env python3
"""
Voice-to-text input tool.
Records audio from microphone, transcribes with Whisper, copies to clipboard.
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
import threading
import warnings

# Audio recording settings
SAMPLE_RATE = 16000
CHANNELS = 1

# Language mapping (code, label)
LANGUAGES = {
    "1": ("en", "EN"),
    "2": ("ru", "RU"),
    "3": ("da", "DA"),
    "4": ("es", "ES"),
}


def print_recording_help(model, language):
    """Print help message during recording."""
    flag = dict((v[0], v[1]) for v in LANGUAGES.values()).get(language, language)
    print(f"Model: {model} | {flag}")
    print("1-EN  2-RU  3-DA  4-ES  Enter-Stop")
    print("-" * 42)


def record_audio(output_path, model, default_language):
    """Record audio from microphone. Returns (success, language_code, next_language)."""
    try:
        import sounddevice as sd
        import numpy as np
        from scipy.io import wavfile
    except ImportError:
        print("pip install sounddevice numpy scipy")
        sys.exit(1)

    language = default_language
    next_language = None
    recording = []
    stop_recording = False
    last_dot_time = time.time()
    dot_count = 0

    def audio_callback(indata, frames, time_info, status):
        recording.append(indata.copy())

    old_settings = termios.tcgetattr(sys.stdin)

    try:
        tty.setcbreak(sys.stdin.fileno())
        print_recording_help(model, language)

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=audio_callback):
            while not stop_recording:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1)
                    if key in LANGUAGES:
                        next_language = LANGUAGES[key][0]
                    stop_recording = True
                else:
                    # Add dot every 2 seconds
                    if time.time() - last_dot_time >= 1:
                        sys.stdout.write(".")
                        sys.stdout.flush()
                        last_dot_time = time.time()
                        dot_count += 1

        print()  # New line after recording

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    if not recording:
        return False, None, next_language

    audio_data = np.concatenate(recording, axis=0)
    audio_int16 = (audio_data * 32767).astype(np.int16)
    wavfile.write(output_path, SAMPLE_RATE, audio_int16)

    return True, language, next_language


class Spinner:
    """Simple spinner for progress indication."""
    def __init__(self):
        self.spinning = False
        self.thread = None
        self.chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def start(self):
        self.spinning = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.start()

    def _spin(self):
        i = 0
        while self.spinning:
            sys.stdout.write(f"\r{self.chars[i % len(self.chars)]} ")
            sys.stdout.flush()
            i += 1
            time.sleep(0.1)

    def stop(self):
        self.spinning = False
        if self.thread:
            self.thread.join()
        sys.stdout.write("\r  \r")
        sys.stdout.flush()


def load_whisper_model(model_name):
    """Load Whisper model."""
    try:
        import whisper
    except ImportError:
        print("pip install openai-whisper")
        sys.exit(1)

    warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")
    return whisper.load_model(model_name)


def transcribe_audio(audio_path, model, language):
    """Transcribe audio using Whisper."""
    result = model.transcribe(audio_path, language=language)
    return result["text"].strip()


def translate_text(text, source_lang, target_lang):
    """Translate text using Google Translate."""
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("pip install deep-translator")
        sys.exit(1)

    translator = GoogleTranslator(source=source_lang, target=target_lang)
    return translator.translate(text)


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
        print("sudo dnf install xclip")
        return False


def main():
    # Relaunch in terminal if not running in one
    if not sys.stdin.isatty():
        script = os.path.abspath(__file__)
        cmd = [
            "xfce4-terminal",
            "--geometry=50x12",
            "--hide-menubar",
            "--hide-toolbar",
            "--hide-scrollbar",
            "--title=Voice Input",
            "-x", "python3", script
        ] + sys.argv[1:]
        subprocess.run(cmd)
        return 0

    parser = argparse.ArgumentParser(description="Voice-to-text input tool")
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="turbo",
        choices=["tiny", "base", "small", "medium", "large", "turbo"],
        help="Whisper model"
    )
    parser.add_argument(
        "-l", "--language",
        type=str,
        default="ru",
        choices=["en", "ru", "da", "es"],
        help="Language (default: ru)"
    )
    args = parser.parse_args()

    # Load model once
    print(f"Loading {args.model} model...")
    whisper_model = load_whisper_model(args.model)
    print("Ready!\n")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        audio_path = tmp_file.name

    current_language = args.language

    try:
        while True:
            success, language, next_language = record_audio(audio_path, args.model, current_language)

            # Update language for next recording
            if next_language:
                current_language = next_language

            if not success:
                continue

            spinner = Spinner()
            spinner.start()
            start_time = time.time()
            text = transcribe_audio(audio_path, whisper_model, language)
            elapsed = time.time() - start_time
            spinner.stop()

            if not text:
                print()
                continue

            # Copy original to clipboard
            copy_to_clipboard(text)

            # Translate to all languages
            all_langs = [("en", "EN"), ("ru", "RU"), ("da", "DA"), ("es", "ES")]
            translations = {}
            for lang_code, _ in all_langs:
                if lang_code == language:
                    translations[lang_code] = text
                else:
                    translations[lang_code] = translate_text(text, language, lang_code)

            word_count = len(text.split())
            print("-" * 42)
            lines = [translations[lang_code] for lang_code, _ in all_langs]
            print("\n".join(lines))
            print("-" * 42)
            print(f"Words: {word_count} | Time: {elapsed:.1f}s")
            print("Press any key...")

            # Wait for any key
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setcbreak(sys.stdin.fileno())
                key = sys.stdin.read(1)
                if key in LANGUAGES:
                    current_language = LANGUAGES[key][0]
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            print()

    except KeyboardInterrupt:
        pass
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
