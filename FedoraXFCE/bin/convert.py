#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
from pathlib import Path
from enum import Enum

FFMPEG = "ffmpeg"

class ConversionMode(Enum):
    TELEGRAM = 1
    AUDIO_ONLY = 2
    VIDEO_SLIDES_1FPS = 3
    VIDEO_SLIDES_1FPS_HALF = 4

# Pick your poison — add more if needed
VIDEO_EXTS = {
    ".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".mts", ".m2ts", ".3gp", ".mpeg", ".mpg", ".ts"
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
      - video:  video_x2/foo-result.mp4
      - audio:  video_x2/foo-audio.m4a
    """
    video_out = outdir / f"{src.stem}-result.mp4"
    audio_out = outdir / f"{src.stem}-audio.m4a"
    return video_out, audio_out

def complress_to_telegram(src: Path, dst: Path) -> None:
    """
    Re-encode to compact H.264 + AAC suitable for mobile viewing:
      - 15 fps
      - half resolution (scale by 0.5)
      - CRF 25, preset slow
      - mono 64k AAC
    """
   
    # Build path: <dst.parent>/half/<dst.name>
    half_dir = dst.parent / "half"
    half_dir.mkdir(parents=True, exist_ok=True)  # make sure it exists
    dst_half = half_dir / dst.name
    
    args = [
        FFMPEG,
        "-y",
        "-i", str(src),
        "-map_metadata", "-1",
        "-max_muxing_queue_size", "512",
        "-vf", "scale=trunc(iw/2):trunc(ih/2):flags=lanczos",
        "-r", "15",
        "-crf", "25",
        "-vcodec", "libx264", "-preset", "slow", "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "1", "-b:a", "64k",
        "-movflags", "+faststart",
        str(dst_half),
    ]
    r = run(args)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "ffmpeg failed (video)")

def extract_audio_compact(src: Path, dst: Path) -> None:
    """
    Audio-only extraction to AAC in M4A container to keep it lightweight:
      - mono 64k AAC (match your video's audio settings)
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

def convert_video_slides_1fps(src: Path, dst: Path, reduce_resolution: bool = False) -> None:
    """
    Convert video to slides at 1fps with optional resolution reduction:
      - 1 fps (for presentations/slides)
      - optionally reduce resolution by half
      - CRF 23, preset slow
      - mono 64k AAC audio
    """
    scale_filter = "scale=trunc(iw/2):trunc(ih/2):flags=lanczos" if reduce_resolution else "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos"
    
    args = [
        FFMPEG,
        "-y",
        "-i", str(src),
        "-map_metadata", "-1",
        "-max_muxing_queue_size", "512",
        "-vf", scale_filter,
        "-r", "1",
        "-crf", "23",
        "-vcodec", "libx264", "-preset", "slow", "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "1", "-b:a", "64k",
        "-movflags", "+faststart",
        str(dst),
    ]
    r = run(args)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "ffmpeg failed (video slides)")

def audio_only_conversion(src: Path, dst: Path) -> None:
    """
    Extract audio only at 64k bitrate (same as extract_audio_compact)
    """
    extract_audio_compact(src, dst)

def should_skip(path: Path) -> bool:
    """Skip already-processed outputs inside result/ to avoid infinite loops."""
    return path.parent.name == "video_x2"

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

def show_conversion_dialog() -> ConversionMode:
    """
    Show interactive dialog to select conversion mode.
    """
    print("\n" + "="*60)
    print("🎬 Video Conversion Tool - Select Conversion Mode")
    print("="*60)
    print("1) Telegram (video: 15fps x2 + audio 64kb)")
    print("2) Only audio 64Kb")
    print("3) Only video slides (1fps)")
    print("4) Only video slides (1fps, x2)")
    print("="*60)
    
    while True:
        try:
            choice = input("\nEnter your choice (1-4): ").strip()
            if choice == "1":
                return ConversionMode.TELEGRAM
            elif choice == "2":
                return ConversionMode.AUDIO_ONLY
            elif choice == "3":
                return ConversionMode.VIDEO_SLIDES_1FPS
            elif choice == "4":
                return ConversionMode.VIDEO_SLIDES_1FPS_HALF
            else:
                print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")
        except (EOFError, KeyboardInterrupt):
            print("\n\n❌ Cancelled by user.")
            sys.exit(0)

def main():
    # No args: operate on current dir, as requested
    root = Path(".").resolve()

    ensure_ffmpeg()

    media_files = find_media_files(root)
    if not media_files:
        print("🤷 No media files found in the current folder. "
              "Try tossing in some .mov/.webm/.avi/.mp4 and friends.")
        sys.exit(0)

    # Show dialog to select conversion mode
    mode = show_conversion_dialog()
    
    outdir = root / mode.name.lower()
    outdir.mkdir(exist_ok=True)

    print(f"\n🚀 Starting conversion with mode: {mode.name}")
    print(f"📁 Processing {len(media_files)} file(s)...")

    exit_code = 0
    for src in media_files:
        video_out, audio_out = make_paths(src, outdir)

        print(f"\n🎬 Source: {src.name}")
        try:
            if mode == ConversionMode.TELEGRAM:
                # Original implementation: video (full + half) + audio
                todo = []
                if not video_out.exists():
                    todo.append("video")
                if not audio_out.exists():
                    todo.append("audio")

                if not todo:
                    print(f"⏭  Skipping (already done): {src.name}")
                    continue

                if "video" in todo and src.suffix.lower() in VIDEO_EXTS:
                    print(f"   ▶ Converting to MP4 → {video_out.name}")
                    complress_to_telegram(src, video_out)
                    if not video_out.exists() or video_out.stat().st_size == 0:
                        raise RuntimeError("Output video missing or empty.")
                    print(f"   ✅ Video done")

                # Extract audio from both video and audio sources
                print(f"   🎧 Extracting audio → {audio_out.name}")
                extract_audio_compact(src, audio_out)
                if not audio_out.exists() or audio_out.stat().st_size == 0:
                    raise RuntimeError("Output audio missing or empty.")
                print(f"   ✅ Audio done")

            elif mode == ConversionMode.AUDIO_ONLY:
                # Only extract audio
                if audio_out.exists():
                    print(f"⏭  Skipping (already done): {src.name}")
                    continue
                print(f"   🎧 Extracting audio only → {audio_out.name}")
                audio_only_conversion(src, audio_out)
                if not audio_out.exists() or audio_out.stat().st_size == 0:
                    raise RuntimeError("Output audio missing or empty.")
                print(f"   ✅ Audio done")

            elif mode == ConversionMode.VIDEO_SLIDES_1FPS:
                # Video slides at 1fps (full resolution)
                if src.suffix.lower() not in VIDEO_EXTS:
                    print(f"⏭  Skipping (not a video): {src.name}")
                    continue
                if video_out.exists():
                    print(f"⏭  Skipping (already done): {src.name}")
                    continue
                print(f"   ▶ Converting to slides (1fps) → {video_out.name}")
                convert_video_slides_1fps(src, video_out, reduce_resolution=False)
                if not video_out.exists() or video_out.stat().st_size == 0:
                    raise RuntimeError("Output video missing or empty.")
                print(f"   ✅ Slides video done")

            elif mode == ConversionMode.VIDEO_SLIDES_1FPS_HALF:
                # Video slides at 1fps (half resolution)
                if src.suffix.lower() not in VIDEO_EXTS:
                    print(f"⏭  Skipping (not a video): {src.name}")
                    continue
                if video_out.exists():
                    print(f"⏭  Skipping (already done): {src.name}")
                    continue
                print(f"   ▶ Converting to slides (1fps, half resolution) → {video_out.name}")
                convert_video_slides_1fps(src, video_out, reduce_resolution=True)
                if not video_out.exists() or video_out.stat().st_size == 0:
                    raise RuntimeError("Output video missing or empty.")
                print(f"   ✅ Slides video done")

        except Exception as e:
            print(f"⚠️  Failed on {src.name}: {e}", file=sys.stderr)
            exit_code = 1

    print("\n🏁 Finished. Check the 'video_x2' folder for your goodies.")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
