#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
from pathlib import Path
from enum import Enum

FFMPEG = "ffmpeg"

class ConversionMode(Enum):
    MERGE_FILES = 0
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
    Re-encode to compact H.264 + AAC suitable for Telegram:
      - 15 fps
      - half resolution (scale by 0.5)
      - CRF 25, preset slow
      - mono 64k AAC
    """
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
        str(dst),
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

def merge_media_files(files: list[Path], output: Path, is_video: bool) -> None:
    """
    Merge multiple media files into one using FFmpeg concat demuxer.
    Files should be in the same format for best results.
    
    Args:
        files: List of media files to merge (sorted)
        output: Output file path
        is_video: True for video files, False for audio files
    """
    if not files:
        raise ValueError("No files to merge")
    
    # Create a temporary file list for FFmpeg concat demuxer
    concat_list = output.parent / "concat_list.txt"
    
    try:
        # Write file list in FFmpeg concat format
        with open(concat_list, "w", encoding="utf-8") as f:
            for file in files:
                # Escape single quotes and write in concat demuxer format
                safe_path = str(file.absolute()).replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")
        
        # Build FFmpeg command for concatenation
        args = [
            FFMPEG,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",  # Copy streams without re-encoding (fast)
            str(output),
        ]
        
        print(f"   > Merging {len(files)} files...")
        r = run(args)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or "ffmpeg merge failed")
            
    finally:
        # Clean up temporary file list
        if concat_list.exists():
            concat_list.unlink()

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

def show_conversion_dialog(media_files: list[Path]) -> ConversionMode:
    """
    Show interactive dialog to select conversion mode.
    Returns selected ConversionMode
    """
    print("\n" + "="*60)
    print("Video Conversion Tool - Select Conversion Mode")
    print("="*60)
    print("0) Merge all files into one (video->video or audio->audio)")
    print("1) Telegram (video: 15fps x2 + audio 64kb)")
    print("2) Only audio 64Kb")
    print("3) Only video slides (1fps)")
    print("4) Only video slides (1fps, x2)")
    print("="*60)
    
    # Show current selection
    if not media_files:
        print("Current selection: Nothing (no media files in folder)")
    elif len(media_files) == 1:
        print(f"Current selection: {media_files[0].name}")
    else:
        print(f"Current selection: All files ({len(media_files)} files)")
    print("="*60)
    
    while True:
        try:
            choice = input("\nEnter your choice (0-4): ").strip()
            if choice == "0":
                return ConversionMode.MERGE_FILES
            elif choice == "1":
                return ConversionMode.TELEGRAM
            elif choice == "2":
                return ConversionMode.AUDIO_ONLY
            elif choice == "3":
                return ConversionMode.VIDEO_SLIDES_1FPS
            elif choice == "4":
                return ConversionMode.VIDEO_SLIDES_1FPS_HALF
            else:
                print("Invalid choice. Please enter 0, 1, 2, 3, or 4.")
        except (EOFError, KeyboardInterrupt):
            print("\n\nCancelled by user.")
            sys.exit(0)

def main():
    # Check for command-line argument: single file name
    if len(sys.argv) > 1:
        # Single file mode: process only the specified file
        filename = sys.argv[1]
        root = Path(".").resolve()
        ensure_ffmpeg()
        
        # Find the specified file
        target_file = root / filename
        if not target_file.exists() or not target_file.is_file():
            print(f"\nError: File '{filename}' not found in current directory")
            sys.exit(1)
        
        # Check if it's a media file
        if target_file.suffix.lower() not in VIDEO_EXTS and target_file.suffix.lower() not in AUDIO_EXTS:
            print(f"\nError: '{filename}' is not a supported media file")
            print(f"Supported formats: {', '.join(sorted(VIDEO_EXTS | AUDIO_EXTS))}")
            sys.exit(1)
        
        media_files = [target_file]
        files_to_process = [target_file]
        scope_label = f"Single file: {filename}"
    else:
        # No args: operate on ALL files in current dir
        root = Path(".").resolve()
        ensure_ffmpeg()
        media_files = find_media_files(root)
        
        # Check if we have files to process
        if not media_files:
            print("\nNo media files found in the current folder. "
                  "Try tossing in some .mov/.webm/.avi/.mp4 and friends.")
            sys.exit(0)
        
        files_to_process = media_files
        scope_label = "All files"
    
    # Show dialog to select conversion mode
    mode = show_conversion_dialog(media_files)
    
    # Handle MERGE_FILES mode separately (processes all files at once)
    if mode == ConversionMode.MERGE_FILES:
        # Separate video and audio files
        video_files = [f for f in files_to_process if f.suffix.lower() in VIDEO_EXTS]
        audio_files = [f for f in files_to_process if f.suffix.lower() in AUDIO_EXTS]
        
        if not video_files and not audio_files:
            print("\nNo video or audio files to merge!")
            sys.exit(0)
        
        outdir = root / mode.name.lower()
        outdir.mkdir(exist_ok=True)
        
        print(f"\nStarting merge operation")
        print(f"Mode: {mode.name}")
        print(f"Scope: {scope_label}")
        
        exit_code = 0
        
        # Merge video files if present
        if video_files:
            if len(video_files) < 2:
                print(f"\nOnly {len(video_files)} video file found - nothing to merge")
            else:
                video_output = outdir / "merged-video.mp4"
                print(f"\nMerging {len(video_files)} video files:")
                for vf in video_files:
                    print(f"  - {vf.name}")
                try:
                    merge_media_files(video_files, video_output, is_video=True)
                    if video_output.exists() and video_output.stat().st_size > 0:
                        print(f"   [OK] Merged video saved to: {video_output.name}")
                    else:
                        raise RuntimeError("Output video missing or empty.")
                except Exception as e:
                    print(f"  WARNING: Failed to merge videos: {e}", file=sys.stderr)
                    exit_code = 1
        
        # Merge audio files if present
        if audio_files:
            if len(audio_files) < 2:
                print(f"\nOnly {len(audio_files)} audio file found - nothing to merge")
            else:
                audio_output = outdir / "merged-audio.m4a"
                print(f"\nMerging {len(audio_files)} audio files:")
                for af in audio_files:
                    print(f"  - {af.name}")
                try:
                    merge_media_files(audio_files, audio_output, is_video=False)
                    if audio_output.exists() and audio_output.stat().st_size > 0:
                        print(f"   [OK] Merged audio saved to: {audio_output.name}")
                    else:
                        raise RuntimeError("Output audio missing or empty.")
                except Exception as e:
                    print(f"  WARNING: Failed to merge audio: {e}", file=sys.stderr)
                    exit_code = 1
        
        print(f"\nFinished. Check the '{mode.name.lower()}' folder for your goodies.")
        sys.exit(exit_code)
    
    # Regular conversion modes (process each file individually)
    outdir = root / mode.name.lower()
    outdir.mkdir(exist_ok=True)

    print(f"\nStarting conversion")
    print(f"Mode: {mode.name}")
    print(f"Scope: {scope_label}")
    print(f"Processing {len(files_to_process)} file(s)...")

    exit_code = 0
    for src in files_to_process:
        video_out, audio_out = make_paths(src, outdir)

        print(f"\nSource: {src.name}")
        try:
            if mode == ConversionMode.TELEGRAM:
                # Original implementation: video (full + half) + audio
                todo = []
                if not video_out.exists():
                    todo.append("video")
                if not audio_out.exists():
                    todo.append("audio")

                if not todo:
                    print(f"  Skipping (already done): {src.name}")
                    continue

                if "video" in todo and src.suffix.lower() in VIDEO_EXTS:
                    print(f"   > Converting to MP4 -> {video_out.name}")
                    complress_to_telegram(src, video_out)
                    if not video_out.exists() or video_out.stat().st_size == 0:
                        raise RuntimeError("Output video missing or empty.")
                    print(f"   [OK] Video done")

                # Extract audio from both video and audio sources
                print(f"   > Extracting audio -> {audio_out.name}")
                extract_audio_compact(src, audio_out)
                if not audio_out.exists() or audio_out.stat().st_size == 0:
                    raise RuntimeError("Output audio missing or empty.")
                print(f"   [OK] Audio done")

            elif mode == ConversionMode.AUDIO_ONLY:
                # Only extract audio
                if audio_out.exists():
                    print(f"  Skipping (already done): {src.name}")
                    continue
                print(f"   > Extracting audio only -> {audio_out.name}")
                audio_only_conversion(src, audio_out)
                if not audio_out.exists() or audio_out.stat().st_size == 0:
                    raise RuntimeError("Output audio missing or empty.")
                print(f"   [OK] Audio done")

            elif mode == ConversionMode.VIDEO_SLIDES_1FPS:
                # Video slides at 1fps (full resolution)
                if src.suffix.lower() not in VIDEO_EXTS:
                    print(f"  Skipping (not a video): {src.name}")
                    continue
                if video_out.exists():
                    print(f"  Skipping (already done): {src.name}")
                    continue
                print(f"   > Converting to slides (1fps) -> {video_out.name}")
                convert_video_slides_1fps(src, video_out, reduce_resolution=False)
                if not video_out.exists() or video_out.stat().st_size == 0:
                    raise RuntimeError("Output video missing or empty.")
                print(f"   [OK] Slides video done")

            elif mode == ConversionMode.VIDEO_SLIDES_1FPS_HALF:
                # Video slides at 1fps (half resolution)
                if src.suffix.lower() not in VIDEO_EXTS:
                    print(f"  Skipping (not a video): {src.name}")
                    continue
                if video_out.exists():
                    print(f"  Skipping (already done): {src.name}")
                    continue
                print(f"   > Converting to slides (1fps, half resolution) -> {video_out.name}")
                convert_video_slides_1fps(src, video_out, reduce_resolution=True)
                if not video_out.exists() or video_out.stat().st_size == 0:
                    raise RuntimeError("Output video missing or empty.")
                print(f"   [OK] Slides video done")

        except Exception as e:
            print(f"  WARNING: Failed on {src.name}: {e}", file=sys.stderr)
            exit_code = 1

    print(f"\nFinished. Check the '{mode.name.lower()}' folder for your goodies.")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
