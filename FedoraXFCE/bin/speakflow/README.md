# SpeakFlow - Voice-to-Text Application

Cross-platform voice-to-text application that records audio on Ctrl+Space and pastes transcribed text into the active application.

## Features

- **Global Hotkey**: Ctrl+Space to toggle recording
- **Offline Speech-to-Text**: OpenAI Whisper (runs locally)
- **System Tray Integration**: Visual feedback for recording state
- **Cross-Platform**: Works on Linux and Windows

## Installation

1. Install system dependencies (Linux only):
```bash
sudo dnf install portaudio
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python main.py
```

2. The system tray icon will appear:
   - **Gray**: Idle (ready to record)
   - **Red**: Recording in progress
   - **Yellow**: Processing/transcribing

3. Press **Ctrl+Space** to start recording
4. Speak your text
5. Press **Ctrl+Space** again to stop recording
6. The transcribed text will be automatically pasted into the active application

## Configuration

Edit `config.py` to customize:

- **WHISPER_MODEL**: Choose model size (tiny, base, small, medium, large)
  - `tiny`: Fastest, least accurate
  - `base`: Good balance (default)
  - `small`: Better accuracy
  - `medium/large`: Best accuracy, slower

- **WHISPER_LANGUAGE**: Set language or None for auto-detect
  - `None`: Auto-detect (default)
  - `"en"`: English
  - `"es"`: Spanish
  - etc.

- **SAMPLE_RATE**: Audio sample rate (16000 Hz recommended for Whisper)

## System Requirements

- Python 3.8+
- Microphone
- Desktop environment with system tray support

## Troubleshooting

### Linux: No microphone access
```bash
sudo usermod -a -G audio $USER
# Log out and log back in
```

### Linux: System tray icon doesn't appear
Ensure you're running a desktop environment with system tray support (XFCE, GNOME, KDE, etc.)

### Whisper model download
On first run, Whisper will download the selected model. This is a one-time operation.

## Architecture

- `main.py`: Main orchestrator and state machine
- `recorder.py`: Audio recording using sounddevice
- `transcriber.py`: Whisper integration
- `hotkey.py`: Global hotkey detection using pynput
- `paster.py`: Text insertion via clipboard + Ctrl+V simulation
- `tray.py`: System tray icon with state visualization
- `config.py`: Configuration settings

## License

MIT
