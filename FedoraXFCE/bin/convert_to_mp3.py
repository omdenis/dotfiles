#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
from pathlib import Path

FFMPEG = "ffmpeg"

def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def ensure_ffmpeg():
    r = run([FFMPEG, "-version"])
    if r.returncode != 0:
        print("❌ ffmpeg not found in PATH. Please install ffmpeg.", file=sys.stderr)
        sys.exit(1)

def make_output_path(src: Path) -> Path:
    return src.with_name(f"{src.stem}-result.mp3")

def extract_to_mp3(src: Path, dst: Path):
    """
    Извлекает аудио и кодирует в MP3 (128k стерео).
    """
    args = [
        FFMPEG,
        "-y",
        "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vn",                # no video
        "-c:a", "libmp3lame", # mp3 encoder
        "-b:a", "128k",       # bitrate
        str(dst),
    ]
    r = run(args)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "ffmpeg failed")

def main():
    if len(sys.argv) < 2:
        print("Usage: python simple_to_mp3.py <path-to-file> [more files...]", file=sys.stderr)
        sys.exit(2)

    ensure_ffmpeg()

    exit_code = 0
    for arg in sys.argv[1:]:
        src = Path(arg).expanduser().resolve()
        if not src.exists() or not src.is_file():
            print(f"❌ Not a file: {src}", file=sys.stderr)
            exit_code = 1
            continue

        dst = make_output_path(src)
        try:
            print(f"🎧 Extracting MP3: {src.name} → {dst.name}")
            extract_to_mp3(src, dst)
            print(f"✅ Done: {dst}")
        except Exception as e:
            print(f"⚠️ Failed: {src.name} — {e}", file=sys.stderr)
            exit_code = 1

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
