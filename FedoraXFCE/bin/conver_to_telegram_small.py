#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
import shlex
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
    # Always output MP4 with -результат suffix
    return src.with_name(f"{src.stem}-result-small.mp4")

def compress_to_mobile_hq(src: Path, dst: Path) -> None:
    """
    Re-encode to compact H.264 + AAC suitable for mobile viewing:
      - ~25 fps
      - Downscale by ~2x with even dimensions
      - CRF 23, preset slow
      - mono 64k AAC (tweak if you prefer stereo: change -ac 1 to -ac 2 and 128k)
    """
    vf = (
        "fps=25,"
        "scale=if(gte(iw\\,2)\\,iw/2\\,iw/2+1):if(gte(ih\\,2)\\,ih/2\\,ih/2+1),"
        "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos"
    )

    args = [
        FFMPEG,
        "-y",  # overwrite output
        # "-hide_banner", "-stats", # "-loglevel", "error",
        "-i", str(src),
        "-map_metadata", "-1",
        "-max_muxing_queue_size", "512",
        "-vf", vf,
        "-crf", "23",
        "-vcodec", "libx264", "-preset", "slow", "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "1", "-b:a", "64k",
        "-movflags", "+faststart",
        str(dst),
    ]
    r = run(args)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "ffmpeg failed")

def main():
    if len(sys.argv) < 2:
        print("Usage: python simple_compress_local.py <path-to-video> [more files...]", file=sys.stderr)
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
            print(f"🎬 Compressing: {src.name} → {dst.name}")
            compress_to_mobile_hq(src, dst)
            # tiny sanity check: ensure output exists and is non-empty
            if not dst.exists() or dst.stat().st_size == 0:
                raise RuntimeError("Output file missing or empty.")
            print(f"✅ Done: {dst}")
        except Exception as e:
            print(f"⚠️ Failed: {src.name} — {e}", file=sys.stderr)
            exit_code = 1

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
