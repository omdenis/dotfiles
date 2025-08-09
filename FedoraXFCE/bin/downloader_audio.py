#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Простой пайплайн:
1) Читает ./files.txt (одна ссылка в строке, строки с # игнорятся)
2) Качает всё в ./src
3) Вынимает аудио (m4a, AAC 128k) в текущую папку

Зависимости:
  - Python 3.8+
  - pip install yt-dlp
  - ffmpeg в PATH (или укажи путь в FFMPGE_PATH ниже)
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
FFMPEG_PATH = "ffmpeg"    # можно указать полный путь, если не в PATH
YTDLP_BIN = "yt-dlp"      # можно указать полный путь, если не в PATH

# ==== Утилиты ====
def run(cmd: str) -> subprocess.CompletedProcess:
    """Запуск команды с выводом ошибок, кидает исключение при ненулевом коде."""
    return subprocess.run(shlex.split(cmd), check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def try_run(cmd: str) -> subprocess.CompletedProcess:
    """Запуск команды без исключения, если что-то пошло не так — вернём результат."""
    return subprocess.run(shlex.split(cmd), check=False, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def trim(s: str) -> str:
    return s.strip()

def ensure_tools():
    # Проверяем наличие ffmpeg
    r = try_run(f"{FFMPEG_PATH} -version")
    if r.returncode != 0:
        print("❌ ffmpeg не найден. Добавь его в PATH или пропиши путь в FFMPEG_PATH.", file=sys.stderr)
        sys.exit(1)
    # Проверяем наличие yt-dlp
    r = try_run(f"{YTDLP_BIN} --version")
    if r.returncode != 0:
        print("❌ yt-dlp не найден. Установи:  pip install yt-dlp  или добавь в PATH.", file=sys.stderr)
        sys.exit(1)

def read_links(path: Path) -> list[str]:
    if not path.exists():
        print(f"❌ Нет файла со ссылками: {path.resolve()}", file=sys.stderr)
        sys.exit(1)
    links: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = trim(line)
        if not line or line.startswith("#"):
            continue
        links.append(line)
    return links

YT_RE = re.compile(r"(youtube\.com|youtu\.be)", re.IGNORECASE)

def safe_filename(s: str) -> str:
    """Чистим строку для безопасного использования как имени файла."""
    # Заменяем запрещённые символы на _
    return re.sub(r'[\\/*?:"<>|]', "_", s)

def safe_name_from_url(url: str) -> str:
    """Имя файла: для YouTube — ID + заголовок, иначе basename."""
    if YT_RE.search(url):
        # Получаем ID и заголовок одной командой
        r = try_run(f'{YTDLP_BIN} --get-id --get-title {shlex.quote(url)}')
        if r.returncode == 0:
            lines = [trim(x) for x in r.stdout.splitlines() if trim(x)]
            if len(lines) >= 2:
                vid_id, title = lines[0], lines[1]
                return safe_filename(f"{vid_id}_{title}")
            elif lines:
                return safe_filename(lines[0])
    # generic: убираем query и расширение
    clean = url.split("?", 1)[0]
    base = Path(clean).name
    stem = Path(base).stem
    stem = stem or f"item_{int(datetime.now().timestamp()*1000)}"
    return safe_filename(stem)

def download_one(url: str, dst_dir: Path, stem: str) -> None:
    """
    Правила:
    - YouTube → yt-dlp -S "res:1080,fps"
    - *.m3u8 → ffmpeg -c copy → .ts
    - остальное → yt-dlp (универсально)
    """
    dst_dir.mkdir(parents=True, exist_ok=True)

    if url.lower().endswith(".m3u8") or ".m3u8?" in url.lower():
        out = dst_dir / f"{stem}.ts"
        cmd = f'{FFMPEG_PATH} -y -hide_banner -loglevel error -i {shlex.quote(url)} -c copy {shlex.quote(str(out))}'
        r = try_run(cmd)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg не смог скачать HLS: {url}\n{r.stderr}")
        return

    if YT_RE.search(url):
        # YouTube
        out_tpl = dst_dir / f"{stem}.%(ext)s"
        cmd = f'{YTDLP_BIN} -S "res:1080,fps" -o {shlex.quote(str(out_tpl))} {shlex.quote(url)}'
    else:
        # Всё остальное отдаём yt-dlp
        out_tpl = dst_dir / f"{stem}.%(ext)s"
        cmd = f'{YTDLP_BIN} -o {shlex.quote(str(out_tpl))} {shlex.quote(url)}'

    r = try_run(cmd)
    if r.returncode != 0:
        raise RuntimeError(f"yt-dlp не смог скачать: {url}\n{r.stderr}")

def transcode_to_m4a(src_file: Path, out_file: Path) -> None:
    # Всегда делаем AAC 128k, выкидываем видео дорожку, faststart
    cmd = (
        f'{FFMPEG_PATH} -y -hide_banner -loglevel error '
        f'-i {shlex.quote(str(src_file))} -vn -c:a aac -b:a 128k -movflags +faststart '
        f'{shlex.quote(str(out_file))}'
    )
    r = try_run(cmd)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg не смог перекодировать {src_file.name} → {out_file.name}\n{r.stderr}")

def main():
    print(f"📄 Список ссылок: {INPUT_FILE.resolve()}")
    print(f"📁 Папка для исходников: {SRC_DIR.resolve()}\n")

    ensure_tools()
    links = read_links(INPUT_FILE)
    if not links:
        print("😶 В файле нет ссылок. Добавь хотя бы одну строку.")
        return

    # === Скачивание ===
    print("🔽 Скачиваем...")
    for i, url in enumerate(links, start=1):
        stem = safe_name_from_url(url)
        # Чтобы избежать коллизий, пронумеруем
        stem = f"{i:02d}_{stem}"
        print(f"  [{i:02d}] {url}  →  src/{stem}.*")
        try:
            download_one(url, SRC_DIR, stem)
        except Exception as e:
            print(f"  ⚠️  Пропускаю (ошибка скачивания): {e}")

    print("✅ Загрузка завершена.\n")

    # === Перекодирование ===
    print("🎧 Перекодируем в m4a...")
    any_done = False
    for src in sorted(SRC_DIR.glob("*")):
        if not src.is_file():
            continue
        stem = src.stem
        out = Path(f"./{stem}.m4a")
        try:
            transcode_to_m4a(src, out)
            print(f"  ✔ {src.name} → {out.name}")
            any_done = True
        except Exception as e:
            print(f"  ⚠️  Пропускаю (ошибка кодирования): {e}")

    if not any_done:
        print("🤷 Нечего перекодировать. Похоже, src пустая?")
    else:
        print("\n🏁 Готово! Исходники в ./src, аудио .m4a — в текущей папке.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Прервано пользователем. Убегаю красиво...")
        sys.exit(130)
