#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import subprocess
from pathlib import Path
import sys
import shutil
import time
import re

FFMPEG_PATH = "ffmpeg"
FFPROBE_PATH = "ffprobe"

BAR_WIDTH = 32  # ширина прогресс-бара

def human_time(sec: float) -> str:
    sec = max(0, int(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_duration_seconds(path: Path) -> float | None:
    try:
        out = subprocess.check_output(
            [
                FFPROBE_PATH, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=nk=1:nw=1",
                str(path)
            ],
            text=True
        ).strip()
        return float(out)
    except Exception:
        return None

def draw_progress(prefix: str, current_sec: float, total_sec: float | None, fps: str | None, speed: str | None):
    cols = shutil.get_terminal_size((100, 20)).columns
    if total_sec and total_sec > 0:
        ratio = min(1.0, current_sec / total_sec)
        done = int(ratio * BAR_WIDTH)
        bar = "█" * done + "░" * (BAR_WIDTH - done)
        percent = f"{ratio*100:5.1f}%"
        eta_str = ""
        if speed:
            m = re.match(r"([0-9]*\.?[0-9]+)x", speed)
            if m:
                sp = float(m.group(1))
                if sp > 0 and total_sec is not None:
                    eta = (total_sec - current_sec) / sp
                    eta_str = f"  ETA {human_time(eta)}"
        prog = f"[{bar}] {percent}  {human_time(current_sec)}"
        if total_sec:
            prog += f"/{human_time(total_sec)}"
        if fps:
            prog += f"  FPS {fps}"
        if speed:
            prog += f"  {speed}{eta_str}"
    else:
        # если длительность неизвестна — рисуем «бесконечный» прогресс
        dots = int(time.time() * 4) % BAR_WIDTH
        bar = ">" + "." * dots + " " * (BAR_WIDTH - dots - 1)
        prog = f"[{bar}]  {human_time(current_sec)}  FPS {fps or '-'}  {speed or '-'}"

    line = f"{prefix} {prog}"
    # ужмём строку под ширину терминала
    if len(line) > cols:
        line = line[:cols - 1]
    print("\r" + line, end="", flush=True)

def encode_mobile_hq(src_file: Path, out_file: Path) -> None:
    # видеофильтр как у тебя: fps 20 + даунскейл/чётные размеры
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
        # магия прогресса — шлём key=value в stdout
        "-progress", "pipe:1",
        str(out_file)
    ]

    # для процентов — берём длительность исходника
    total = get_duration_seconds(src_file)

    # печатаем шапку с параметрами
    print(f"\n🎬 Файл: {src_file.name}")
    if total:
        print(f"⏱️  Длительность: {human_time(total)}")
    print("⚙️  Параметры: libx264 main, CRF 23, preset slow, 20 fps, AAC 64k mono, yuv420p, +faststart")
    print(f"📦 Выход: {out_file.name}\n")

    # запускаем и парсим прогресс
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    out_time_ms = 0.0
    cur_fps = None
    cur_speed = None
    last_draw = 0.0

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, val = line.split("=", 1)
            if key == "out_time_ms":
                try:
                    out_time_ms = float(val) / 1000.0
                except ValueError:
                    pass
            elif key == "fps":
                cur_fps = val
            elif key == "speed":
                cur_speed = val
            elif key == "progress":
                now = time.time()
                # не спамим — обновляем ~10 раз в секунду
                if now - last_draw >= 0.1 or val == "end":
                    draw_progress("🚀", out_time_ms, total, cur_fps, cur_speed)
                    last_draw = now
                if val == "end":
                    break

        proc.wait()
        # финальная строка
        draw_progress("✅", total or out_time_ms, total, cur_fps, cur_speed)
        print()  # перевод строки
        if proc.returncode != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(stderr.strip() or "ffmpeg failed")
    finally:
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()

def main():
    parser = argparse.ArgumentParser(
        description="Конвертилка в Telegram-совместный MP4 с живым прогрессом (_tg.mp4)."
    )
    parser.add_argument(
        "inputs",
        type=Path,
        nargs="+",
        help="Один или несколько видеофайлов"
    )
    args = parser.parse_args()

    for src_file in args.inputs:
        if not src_file.exists():
            print(f"💥 Файл не найден: {src_file}", file=sys.stderr)
            continue

        out_file = src_file.with_name(src_file.stem + "_tg.mp4")
        try:
            encode_mobile_hq(src_file, out_file)
            print(f"🎉 Готово: {src_file.name} → {out_file.name}\n")
        except Exception as e:
            print(f"💣 Ошибка при кодировании {src_file.name}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
