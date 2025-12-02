#!/usr/bin/env python3
"""
mp3_to_mp4.py — convert an audio file (mp3/wav/etc.) + optional image into an MP4
optimized for YouTube (H.264/AAC, yuv420p, faststart).
"""
import argparse
import shutil
import subprocess
from pathlib import Path
import sys

def ensure_ffmpeg():
    if shutil.which("ffmpeg") is None:
        sys.exit("Error: ffmpeg not found in PATH. Please install ffmpeg and try again.")

def build_cmd(audio, image, out, fps, width, height, abr, crf):
    # Common flags
    vf_chain = []
    inputs = []
    maps = []

    if image:
        # Loop the still image to cover the full audio duration, scale & pad to target resolution
        inputs += ["-loop", "1", "-i", image]
        vf_chain.append(
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        )
        maps.append("-map:v:0")
    else:
        # Generate a solid background if no image is provided
        # We'll create a color source at target resolution
        inputs += ["-f", "lavfi", "-i", f"color=size={width}x{height}:rate={fps}:color=black"]
        maps.append("-map:v:0")

    # Audio input
    inputs += ["-i", audio]
    maps += ["-map:a:0"]

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-crf", str(crf),
        "-c:a", "aac",
        "-b:a", f"{abr}k",
        "-shortest",               # stop when the shortest stream (audio) ends
        "-movflags", "+faststart", # better for streaming
    ] + maps + [
        out
    ]

    # If we had an image, add the video filter chain
    if image:
        # Insert -vf just before mapping/output
        insert_at = cmd.index("-shortest")
        cmd[insert_at:insert_at] = ["-vf", ",".join(vf_chain)]

    return cmd

def main():
    parser = argparse.ArgumentParser(description="Convert audio + optional image to MP4 for YouTube.")
    parser.add_argument("audio", help="Path to audio file (mp3/wav/m4a/etc.)")
    parser.add_argument("-i", "--image", help="Path to a cover image (jpg/png). If omitted, a black background is used.")
    parser.add_argument("-o", "--out", help="Output MP4 path (default: <audio-stem>.mp4)")
    parser.add_argument("--fps", type=int, default=30, help="Video framerate (default: 30)")
    parser.add_argument("--width", type=int, default=1920, help="Video width (default: 1920)")
    parser.add_argument("--height", type=int, default=1080, help="Video height (default: 1080)")
    parser.add_argument("--abr", type=int, default=192, help="Audio bitrate in kbps (default: 192)")
    parser.add_argument("--crf", type=int, default=18, help="x264 CRF quality (lower=better; default: 18)")
    args = parser.parse_args()

    ensure_ffmpeg()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        sys.exit(f"Error: audio file not found: {audio_path}")

    image_path = None
    if args.image:
        image_path = Path(args.image)
        if not image_path.exists():
            sys.exit(f"Error: image file not found: {image_path}")

    out_path = Path(args.out) if args.out else audio_path.with_suffix(".mp4")

    cmd = build_cmd(
        audio=str(audio_path),
        image=str(image_path) if image_path else None,
        out=str(out_path),
        fps=args.fps,
        width=args.width,
        height=args.height,
        abr=args.abr,
        crf=args.crf
    )

    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        print(f"Done! Output: {out_path}")
    except subprocess.CalledProcessError as e:
        sys.exit(f"ffmpeg failed with exit code {e.returncode}")

if __name__ == "__main__":
    main()
