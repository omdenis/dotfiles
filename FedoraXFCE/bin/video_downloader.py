import os
import subprocess
from pathlib import Path
from yt_dlp import YoutubeDL

# === Конфигурация ===
BASE_DIR = Path.home() / "video"
INPUT_FILE = BASE_DIR / "files.txt"
TEMP_DIR = BASE_DIR / "01_downloaded"
SLIDES_DIR = BASE_DIR / "02_slides"
FFMPEG_PATH = str(Path.home() / "apps/ffmpeg/ffmpeg")  

# === Инициализация директорий ===
for directory in [TEMP_DIR, SLIDES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
INPUT_FILE.touch()

print(f"📁 Рабочие директории:\n - Скачанные: {TEMP_DIR}\n - Пережатые: {SLIDES_DIR}\n - Файл со ссылками: {INPUT_FILE}\n")

# === Сквозная нумерация ===
def pad_number(n):
    return f"{n:03d}"

# === yt-dlp настройки ===
yt_opts = {
    "format": "bv*+ba/b",
    "quiet": True,
    "no_warnings": True,
    "outtmpl": str(TEMP_DIR / "%(filename)s"),
    "noplaylist": True,
}

def download_youtube(url, number):
    with YoutubeDL(yt_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        video_id = info.get("id")
        filename_template = f"{pad_number(number)}_{video_id}.%(ext)s"
        yt_opts["outtmpl"] = str(TEMP_DIR / filename_template)
        ydl.params.update(yt_opts)
        ydl.download([url])
        return video_id, TEMP_DIR / f"{pad_number(number)}_{video_id}.{info.get('ext', 'mp4')}"

def download_m3u8(url, number):
    name = Path(url).stem
    out_file = TEMP_DIR / f"{pad_number(number)}_{name}.ts"
    cmd = [
        FFMPEG_PATH,
        "-hide_banner", "-y",
        "-i", url,
        "-c", "copy",
        str(out_file)
    ]
    subprocess.run(cmd, stdin=subprocess.DEVNULL)
    return name, out_file

def reencode_to_telegram(input_path, output_path):
    cmd = [
        FFMPEG_PATH,
        "-hide_banner", "-y",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", "veryslow",
        "-crf", "28",
        "-g", "300",
        "-keyint_min", "300",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ]
    subprocess.run(cmd, stdin=subprocess.DEVNULL)

# === Основной цикл ===
with INPUT_FILE.open("r") as f:
    counter = 1
    for line in f:
        url = line.strip()
        if not url or url.startswith("#"):
            continue

        print(f"➡️ Обрабатываем: {url}")
        try:
            if "youtube.com" in url or "youtu.be" in url:
                name, source_file = download_youtube(url, counter)
            elif url.endswith(".m3u8"):
                name, source_file = download_m3u8(url, counter)
            else:
                print(f"⚠️ Неизвестный формат URL: {url}")
                continue

            output_file = SLIDES_DIR / f"{pad_number(counter)}_{name}.mp4"
            print(f"📦 Перекодируем: {output_file.name}")
            reencode_to_telegram(source_file, output_file)
            print(f"✅ Готово: {output_file}\n")
            counter += 1

        except Exception as e:
            print(f"❌ Ошибка обработки {url}: {e}")

print(f"🎉 Всё завершено! Готовые видео в: {SLIDES_DIR}")

