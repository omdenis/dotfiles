import os
import subprocess
from pathlib import Path
from yt_dlp import YoutubeDL

# === Paths ===
BASE_DIR = Path.home() / "video"
INPUT_FILE = BASE_DIR / "files.txt"
TEMP_DIR = BASE_DIR / "01_downloaded"
SLIDES_DIR = BASE_DIR / "02_slides"
FFMPEG = Path.home() / "apps/ffmpeg/ffmpeg"

# === Init directories ===
TEMP_DIR.mkdir(parents=True, exist_ok=True)
SLIDES_DIR.mkdir(parents=True, exist_ok=True)
INPUT_FILE.touch()

print("📁 Working directories:")
print(f" - Downloads: {TEMP_DIR}")
print(f" - Encoded slides: {SLIDES_DIR}")
print(f" - URL list file: {INPUT_FILE}")
print()

# === Format number with leading zeroes ===
def pad_number(n):
    return f"{n:03d}"

# === Start processing ===
with INPUT_FILE.open("r", encoding="utf-8") as f:
    counter = 1
    for raw_url in f:
        url = raw_url.strip()
        if not url or url.startswith("#"):
            continue

        print(f"➡️ Processing: {url}")

        num = pad_number(counter)
        filename = ""
        safe_name = ""

        # === YouTube handling ===
        if "youtube.com" in url or "youtu.be" in url:
            print("🎥 YouTube → yt-dlp")
            try:
                yt_id = subprocess.check_output(
                    ["yt-dlp", "--get-id", url], text=True
                ).strip()
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to get YouTube ID: {e}")
                continue

            safe_name = yt_id
            output_template = f"{num}_{safe_name}.%(ext)s"
            ydl_opts = {
                "outtmpl": str(TEMP_DIR / output_template),
                "format": "bv*+ba/b",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "source_address": "0.0.0.0",
            }

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                print(f"❌ Download failed: {e}")
                continue

            # Find the downloaded file
            possible_files = list(TEMP_DIR.glob(f"{num}_{safe_name}.*"))
            if not possible_files:
                print("❌ Downloaded file not found.")
                continue

            filename = str(sorted(possible_files, key=os.path.getmtime)[-1])

        # === m3u8 handling ===
        elif url.endswith(".m3u8"):
            print("🌐 .m3u8 → ffmpeg")
            base = Path(url).stem
            safe_name = base
            filename = TEMP_DIR / f"{num}_{safe_name}.ts"

            try:
                subprocess.run(
                    [str(FFMPEG), "-y", "-i", url, "-c", "copy", str(filename)],
                    check=True,
                    stdin=subprocess.DEVNULL
                )
            except subprocess.CalledProcessError as e:
                print(f"❌ m3u8 download error: {e}")
                continue

        else:
            print(f"⚠️ Unsupported URL format: {url}")
            continue

        # === Re-encode ===
        output_name = f"{num}_{safe_name}.mp4"
        output_path = SLIDES_DIR / output_name

        print(f"📦 Re-encoding for Telegram: {output_name}")
        ffmpeg_cmd = [
            str(FFMPEG),
            "-y",
            "-i", str(filename),
            "-hide_banner",
            "-loglevel", "error",
            "-threads", "4",
            "-map_metadata", "-1",
            "-max_muxing_queue_size", "512",
            "-filter:v", "fps=2,crop=iw:ih-0:0:0,scale=iw/1:-2",
            "-crf", "30",
            "-r", "2",
            "-vcodec", "libx264",
            "-profile:v", "main",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "64k",
            "-ac", "1",
            "-tune", "stillimage",
            "-preset", "faster",
            "-movflags", "+faststart",
            str(output_path)
        ]

        try:
            subprocess.run(ffmpeg_cmd, check=True, stdin=subprocess.DEVNULL)
            print(f"✅ Saved: {output_path}\n")
        except subprocess.CalledProcessError as e:
            print(f"❌ ffmpeg error: {e}")
            continue

        counter += 1

print(f"🎉 All done! Encoded videos are in '{SLIDES_DIR}'.")
