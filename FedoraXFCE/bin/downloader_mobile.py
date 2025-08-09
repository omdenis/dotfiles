#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Пайплайн:
1) Читает ./files.txt (одна ссылка в строке, строки с # игнорятся)
2) Качает всё в ./src
3) Перекодирует каждый файл в Mobile HQ .mp4 (как в исходном bash)
4) Извлекает аудио дорожку в .m4a
"""

import subprocess
import sys
import shlex
import re
from pathlib import Path
from datetime import datetime

# ==== Настройки ====
INPUT_FILE = Path("./files.txt")
SRC_DIR = Path("./src")
RESULT_DIR = Path("./result")
FFMPEG_PATH = Path("~/apps/ffmpeg/ffmpeg").expanduser()
YTDLP_BIN = "yt-dlp"

# ==== Утилиты ====
def run_list(args: list[str], check: bool = True):
    return subprocess.run(args, check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def try_run(cmd: str):
    return subprocess.run(shlex.split(cmd), check=False, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def trim(s: str) -> str:
    return s.strip()

def ensure_tools():
    for tool, name in [(FFMPEG_PATH, "ffmpeg"), (YTDLP_BIN, "yt-dlp")]:
        r = try_run(f"{tool} --version")
        if r.returncode != 0:
            print(f"❌ {name} не найден. Установи или пропиши путь в переменной.", file=sys.stderr)
            sys.exit(1)

def read_links(path: Path) -> list[str]:
    if not path.exists():
        print(f"❌ Нет файла со ссылками: {path.resolve()}", file=sys.stderr)
        sys.exit(1)
    return [trim(l) for l in path.read_text(encoding="utf-8").splitlines()
            if trim(l) and not l.strip().startswith("#")]

YT_RE = re.compile(r"(youtube\.com|youtu\.be)", re.IGNORECASE)

def safe_filename(s: str) -> str:
    s = re.sub(r'[\\/*?:"<>|]', "_", s)
    s = "".join(ch for ch in s if ch >= " " and ch != "\x7f").strip()
    return s or f"item_{int(datetime.now().timestamp()*1000)}"

def safe_name_from_url(url: str) -> str:
    if YT_RE.search(url):
        r = try_run(f'{YTDLP_BIN} --get-id --get-title {shlex.quote(url)}')
        if r.returncode == 0:
            lines = [trim(x) for x in r.stdout.splitlines() if trim(x)]
            if len(lines) >= 2:
                return safe_filename(f"{lines[0]}_{lines[1]}")
            elif lines:
                return safe_filename(lines[0])
    clean = url.split("?", 1)[0]
    return safe_filename(Path(clean).stem)

def download_one(url: str, dst_dir: Path, stem: str) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    if url.lower().endswith(".m3u8") or ".m3u8?" in url.lower():
        out = dst_dir / f"{stem}.ts"
        args = [FFMPEG_PATH, "-y", "-hide_banner", "-loglevel", "error",
                "-i", url, "-c", "copy", str(out)]
        res = run_list(args, check=False)
        if res.returncode != 0:
            raise RuntimeError(f"ffmpeg не смог скачать HLS: {url}\n{res.stderr}")
        return
    out_tpl = dst_dir / f"{stem}.%(ext)s"
    if YT_RE.search(url):
        cmd = f'{YTDLP_BIN} -S "res:1080,fps" -o {shlex.quote(str(out_tpl))} {shlex.quote(url)}'
    else:
        cmd = f'{YTDLP_BIN} -o {shlex.quote(str(out_tpl))} {shlex.quote(url)}'
    res = try_run(cmd)
    if res.returncode != 0:
        raise RuntimeError(f"yt-dlp не смог скачать: {url}\n{res.stderr}")

def encode_mobile_hq(src_file: Path, out_file: Path) -> None:
    vf = (
        "fps=20,"
        "scale=if(gte(iw\\,2)\\,iw/2\\,iw/2+1):if(gte(ih\\,2)\\,ih/2\\,ih/2+1),"
        "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos"
    )
    args = [
        FFMPEG_PATH, "-y", "-i", str(src_file),
        "-hide_banner", "-nostats", "-loglevel", "error",
        "-threads", "4",
        "-map_metadata", "-1",
        "-max_muxing_queue_size", "512",
        "-vf", vf,
        "-crf", "23",
        "-vcodec", "libx264", "-preset", "slow", "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "1", "-b:a", "64k",
        "-movflags", "+faststart",
        str(out_file)
    ]
    res = run_list(args, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Ошибка кодирования {src_file.name} → {out_file.name}\n{res.stderr}")

def extract_audio(src_file: Path, out_file: Path) -> None:
    args = [
        FFMPEG_PATH, "-y", "-i", str(src_file),
        "-hide_banner", "-nostats", "-loglevel", "error",
        "-vn", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out_file)
    ]
    res = run_list(args, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Ошибка извлечения аудио {src_file.name} → {out_file.name}\n{res.stderr}")

def main():
    print(f"📄 Список ссылок: {INPUT_FILE.resolve()}")
    print(f"📁 Папка для исходников: {SRC_DIR.resolve()}\n")
    # ensure_tools()

    links = read_links(INPUT_FILE)
    if not links:
        print("😶 В файле нет ссылок.")
        return

    print("🔽 Скачиваем...")
    for i, url in enumerate(links, start=1):
        stem = f"{i:02d}_{safe_name_from_url(url)}"
        print(f"  [{i:02d}] {url}  →  src/{stem}.*")
        try:
            download_one(url, SRC_DIR, stem)
        except Exception as e:
            print(f"  ⚠️  Пропуск: {e}")
    print("✅ Загрузка завершена.\n")

    print("🎬 Перекодируем (Mobile HQ) и извлекаем аудио...")
    any_done = False
    for src in sorted(SRC_DIR.glob("*")):
        if not src.is_file():
            continue
        stem = src.stem
        out_mp4 = Path(f"./{RESULT_DIR}/{stem}.mp4")
        out_m4a = Path(f"./{RESULT_DIR}/{stem}.m4a")
        try:
            encode_mobile_hq(src, out_mp4)
            extract_audio(src, out_m4a)
            print(f"  ✔ {src.name} → {out_mp4.name} + {out_m4a.name}")
            any_done = True
        except Exception as e:
            print(f"  ⚠️  Ошибка: {e}")

    if not any_done:
        print("🤷 Похоже, src пустая?")
    else:
        print("\n🏁 Готово! Исходники в ./src, MP4 и M4A — в текущей папке.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Прервано пользователем.")
        sys.exit(130)
