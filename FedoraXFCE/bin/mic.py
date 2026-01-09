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
            # First dot immediately
            sys.stdout.write(".")
            sys.stdout.flush()
            last_dot_time = time.time()

            while not stop_recording:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1)
                    if key in LANGUAGES:
                        next_language = LANGUAGES[key][0]
                    stop_recording = True
                else:
                    # Add dot every 0.5 seconds
                    if time.time() - last_dot_time >= 0.5:
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


def speak_text(text, lang="da"):
    """Speak text using gTTS."""
    try:
        from gtts import gTTS
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
        import pygame
    except ImportError:
        print("pip install gtts pygame")
        return

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tts_path = f.name

    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(tts_path)

        pygame.mixer.init()
        pygame.mixer.music.load(tts_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.quit()
    finally:
        if os.path.exists(tts_path):
            os.remove(tts_path)


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
        "--listen",
        type=str,
        default=None,
        choices=["en", "ru", "da", "es"],
        help="Language to listen (default: ru)"
    )
    parser.add_argument(
        "--clipboard",
        type=str,
        default=None,
        choices=["en", "ru", "da", "es"],
        help="Language to copy to clipboard (default: en)"
    )
    parser.add_argument(
        "--speak",
        type=str,
        default=None,
        choices=["en", "ru", "da", "es"],
        help="Language to speak (default: da)"
    )
    args = parser.parse_args()

    # Configuration presets
    PRESETS = {
        "1": ("ru", "en", "da"),
        "2": ("ru", "ru", "da"),
        "3": ("ru", "en", "en"),
    }

    # If no language args provided, show menu
    if args.listen is None and args.clipboard is None and args.speak is None:
        print("Select configuration:")
        print("1) RU -> EN -> DA (listen RU, copy EN, speak DA)")
        print("2) RU -> RU -> DA (listen RU, copy RU, speak DA)")
        print("3) RU -> EN -> EN (listen RU, copy EN, speak EN)")
        print("-" * 42)

        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            while True:
                key = sys.stdin.read(1)
                if key in PRESETS:
                    args.listen, args.clipboard, args.speak = PRESETS[key]
                    break
                elif key == "\n" or key == "\r":
                    args.listen, args.clipboard, args.speak = PRESETS["1"]
                    break
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    else:
        # Set defaults for any missing args
        args.listen = args.listen or "ru"
        args.clipboard = args.clipboard or "en"
        args.speak = args.speak or "da"

    print(f"Config: {args.listen.upper()} -> {args.clipboard.upper()} -> {args.speak.upper()}")

    # Load model once
    print(f"Loading {args.model} model...")
    whisper_model = load_whisper_model(args.model)
    print("Ready!\n")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        audio_path = tmp_file.name

    current_language = args.listen

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

            # Translate to all languages
            all_langs = [("en", "EN"), ("ru", "RU"), ("da", "DA"), ("es", "ES")]
            translations = {}
            for lang_code, _ in all_langs:
                if lang_code == language:
                    translations[lang_code] = text
                else:
                    translations[lang_code] = translate_text(text, language, lang_code)

            # Copy selected language to clipboard
            copy_to_clipboard(translations[args.clipboard])

            word_count = len(text.split())
            print("-" * 42)
            lines = [translations[lang_code] for lang_code, _ in all_langs]
            print("\n\n".join(lines))
            print("-" * 42)
            print(f"Words: {word_count} | Time: {elapsed:.1f}s")

            # Speak selected language
            speak_text(translations[args.speak], args.speak)

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
