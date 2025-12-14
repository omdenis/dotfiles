#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path
import sys

FFMPEG_PATH = "ffmpeg"


def run_list(args, check=True):
    """Запуск процесса и возврат результата."""
    return subprocess.run(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check
    )


def encode_mobile_hq(src_file: Path, out_file: Path) -> None:
    vf = (
        "fps=25,"
    )
    args = [
        FFMPEG_PATH, "-y", "-i", str(src_file),
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
        raise RuntimeError(
            f"Ошибка кодирования {src_file.name} → {out_file.name}\n{res.stderr}"
        )


def main():
    parser = argparse.ArgumentParser(description="Конвертилка видосов в Telegram-совместимый mp4")
    parser.add_argument("input", type=Path, help="Исходный файл видео")

    args = parser.parse_args()

    src_file = args.input
    if not src_file.exists():
        print(f"Файл {src_file} не найден!", file=sys.stderr)
        sys.exit(1)

    out_file = src_file.with_name(src_file.stem + "_tg.mp4")

    try:
        encode_mobile_hq(src_file, out_file)
        print(f"✅ Готово! {src_file.name} → {out_file.name}")
    except Exception as e:
        print(f"💥 Ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
