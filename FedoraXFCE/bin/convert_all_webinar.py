#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
from pathlib import Path

FFMPEG = "ffmpeg"

# Pick your poison — add more if needed
VIDEO_EXTS = {
    ".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".mts", ".m2ts", ".3gp", ".mpeg", ".mpg"
}
AUDIO_EXTS = {
    ".wav", ".mp3", ".aac", ".m4a", ".flac", ".ogg", ".oga", ".wma", ".aif", ".aiff", ".opus"
}
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS

def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def ensure_ffmpeg():
    r = run([FFMPEG, "-version"])
    if r.returncode != 0:
        print("❌ ffmpeg not found in PATH. Please install ffmpeg.", file=sys.stderr)
        sys.exit(1)

def make_paths(src: Path, outdir: Path) -> tuple[Path, Path]:
    """
    For a source file foo.mov:
      - video:  result/foo-result.mp4
      - audio:  result/foo-audio.m4a
    """
    video_out = outdir / f"{src.stem}-result.mp4"
    audio_out = outdir / f"{src.stem}-audio.m4a"
    return video_out, audio_out

def compress_to_mobile_hq(src: Path, dst: Path) -> None:
    """
    Re-encode to compact H.264 + AAC suitable for mobile viewing:
      - ~25 fps
      - (optional) downscale logic can be tweaked in vf
      - CRF 23, preset slow
      - mono 64k AAC (change -ac 1 to -ac 2 and 128k if you want stereo)
    """
    vf = (
        "fps=3"
        # ,scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos
    )

    args = [
        FFMPEG,
        "-y",
        "-i", str(src),
        "-map_metadata", "-1",
        "-max_muxing_queue_size", "512",
        "-vf", vf,
        "-tune", "stillimage",
        "-crf", "25",
        "-vcodec", "libx264", "-preset", "slow", "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "1", "-b:a", "64k",
        "-movflags", "+faststart",
        str(dst),
    ]
    r = run(args)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "ffmpeg failed (video)")

def extract_audio_compact(src: Path, dst: Path) -> None:
    """
    Audio-only extraction to AAC in M4A container to keep it lightweight:
      - mono 64k AAC (match your video’s audio settings)
    """
    args = [
        FFMPEG,
        "-y",
        "-i", str(src),
        "-map_metadata", "-1",
        "-vn",
        "-c:a", "aac", "-ac", "1", "-b:a", "64k",
        str(dst),
    ]
    r = run(args)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "ffmpeg failed (audio)")

def should_skip(path: Path) -> bool:
    """Skip already-processed outputs inside result/ to avoid infinite loops."""
    return path.parent.name == "webinar"

def find_media_files(root: Path) -> list[Path]:
    files = []
    for p in sorted(root.iterdir()):
        if not p.is_file():
            continue
        if should_skip(p):
            continue
        if p.suffix.lower() in MEDIA_EXTS:
            files.append(p)
    return files

def main():
    # No args: operate on current dir, as requested
    root = Path(".").resolve()

    ensure_ffmpeg()

    outdir = root / "webinar"
    outdir.mkdir(exist_ok=True)

    media_files = find_media_files(root)
    if not media_files:
        print("🤷 No media files found in the current folder. "
              "Try tossing in some .mov/.webm/.avi/.mp4 and friends.")
        sys.exit(0)

    exit_code = 0
    for src in media_files:
        video_out, audio_out = make_paths(src, outdir)

        # Don’t redo finished work
        todo = []
        if not video_out.exists():
            todo.append("video")
        if not audio_out.exists():
            todo.append("audio")

        if not todo:
            print(f"⏭  Skipping (already done): {src.name}")
            continue

        print(f"\n🎬 Source: {src.name}")
        try:
            if "video" in todo and src.suffix.lower() in VIDEO_EXTS:
                print(f"   ▶ Converting to MP4 → {video_out.name}")
                compress_to_mobile_hq(src, video_out)
                if not video_out.exists() or video_out.stat().st_size == 0:
                    raise RuntimeError("Output video missing or empty.")
                print(f"   ✅ Video done")

            # Extract audio from both video and audio sources (re-encode for consistency)
            print(f"   🎧 Extracting audio → {audio_out.name}")
            extract_audio_compact(src, audio_out)
            if not audio_out.exists() or audio_out.stat().st_size == 0:
                raise RuntimeError("Output audio missing or empty.")
            print(f"   ✅ Audio done")

        except Exception as e:
            print(f"⚠️  Failed on {src.name}: {e}", file=sys.stderr)
            exit_code = 1

    print("\n🏁 Finished. Check the 'result' folder for your goodies.")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
