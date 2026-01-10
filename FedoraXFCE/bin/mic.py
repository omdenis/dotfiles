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

# Model cycle for '0' key
MODEL_CYCLE = ["turbo", "tiny", "base", "small", "medium", "large"]


def print_recording_help(model, language):
    """Print help message during recording."""
    flag = dict((v[0], v[1]) for v in LANGUAGES.values()).get(language, language)
    print(f"Model: {model} | {flag}")
    print("1-EN  2-RU  3-DA  4-ES  0-Model  Enter-Stop")
    print("-" * 42)


def record_audio(output_path, model, default_language):
    """Record audio from microphone. Returns (success, language_code, next_language, next_model)."""
    try:
        import sounddevice as sd
        import numpy as np
        from scipy.io import wavfile
    except ImportError:
        print("pip install sounddevice numpy scipy")
        sys.exit(1)

    language = default_language
    next_language = None
    next_model = None
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
                    elif key == "0":
                        current_idx = MODEL_CYCLE.index(model) if model in MODEL_CYCLE else 0
                        next_model = MODEL_CYCLE[(current_idx + 1) % len(MODEL_CYCLE)]
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
        return False, None, next_language, next_model

    audio_data = np.concatenate(recording, axis=0)
    audio_int16 = (audio_data * 32767).astype(np.int16)
    wavfile.write(output_path, SAMPLE_RATE, audio_int16)

    return True, language, next_language, next_model


class DotProgress:
    """Shows dots during long operations."""
    def __init__(self, interval=0.5):
        self.running = False
        self.thread = None
        self.interval = interval

    def start(self):
        self.running = True
        sys.stdout.write(".")
        sys.stdout.flush()
        self.thread = threading.Thread(target=self._dots)
        self.thread.start()

    def _dots(self):
        last_time = time.time()
        while self.running:
            time.sleep(0.1)
            if self.running and time.time() - last_time >= self.interval:
                sys.stdout.write(".")
                sys.stdout.flush()
                last_time = time.time()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        print()


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


def prepare_speech(text, lang="da"):
    """Prepare speech audio file using gTTS. Returns path to audio file."""
    try:
        from gtts import gTTS
    except ImportError:
        print("pip install gtts")
        return None

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tts_path = f.name

    tts = gTTS(text=text, lang=lang)
    tts.save(tts_path)
    return tts_path


def play_speech(tts_path):
    """Play prepared speech audio file."""
    if not tts_path:
        return

    try:
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
        import pygame
    except ImportError:
        print("pip install pygame")
        return

    try:
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
        default="base",
        choices=["tiny", "base", "small", "medium", "turbo"],
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
    current_model = args.model

    try:
        while True:
            success, language, next_language, next_model = record_audio(audio_path, current_model, current_language)

            # Update language for next recording
            if next_language:
                current_language = next_language

            # Update model and reload if changed
            if next_model:
                current_model = next_model
                print(f"Switching to {current_model} model...")
                whisper_model = load_whisper_model(current_model)
                print("Ready!\n")
                continue

            if not success:
                continue

            # Transcribe with dots
            dots = DotProgress()
            dots.start()
            start_time = time.time()
            text = transcribe_audio(audio_path, whisper_model, language)
            elapsed = time.time() - start_time
            dots.stop()

            if not text:
                continue

            # Copy raw transcription immediately
            copy_to_clipboard(text)

            # Translate to all languages with dots
            dots = DotProgress()
            dots.start()
            all_langs = [("en", "EN"), ("ru", "RU"), ("da", "DA"), ("es", "ES")]
            translations = {}
            for lang_code, _ in all_langs:
                if lang_code == language:
                    translations[lang_code] = text
                else:
                    translations[lang_code] = translate_text(text, language, lang_code)
            dots.stop()

            # Prepare speech with dots
            dots = DotProgress()
            dots.start()
            tts_path = prepare_speech(translations[args.speak], args.speak)
            dots.stop()

            # Copy selected language to clipboard
            copy_to_clipboard(translations[args.clipboard])

            # Show results
            word_count = len(text.split())
            print("-" * 42)
            lines = [translations[lang_code] for lang_code, _ in all_langs]
            print("\n\n".join(lines))
            print("-" * 42)
            print(f"Words: {word_count} | Time: {elapsed:.1f}s")

            # Play speech
            play_speech(tts_path)

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
