# sudo dnf install python3-pip
# pip install vosk
# pip install sounddevice
# sudo dnf install portaudio portaudio-devel
# pip install --force-reinstall sounddevice
# wget https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
# mkdir -p ~/models/vosk
# unzip vosk-model-en-us-0.22.zip -d ~/models/vosk

from vosk import Model, KaldiRecognizer
import sounddevice as sd
import json
import subprocess

import os
model = Model(os.path.expanduser("~/models/vosk/vosk-model-en-us-0.22"))

rec = KaldiRecognizer(model, 16000)

def callback(indata, frames, time, status):
    # indata is already bytes in RawInputStream ✅
    if rec.AcceptWaveform(indata):
        res = json.loads(rec.Result())
        print(res.get("text", ""))
    else:
        # partial = json.loads(rec.PartialResult())["partial"]
        pass

with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                       channels=1, callback=callback):
    print("Speak now...")
    import time as _t
    while True:
        _t.sleep(0.1)
