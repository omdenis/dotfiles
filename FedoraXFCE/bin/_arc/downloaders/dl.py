import asyncio
import subprocess
import os
import re
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv


async def main():
    load_dotenv(os.path.expanduser("~/.env"))
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    bot = Bot(token=BOT_TOKEN)

    tg_url = input("Введи ссылку на тему в канале (вида https://t.me/c/...): ").strip()
    try:
        chat_id, thread_id = parse_telegram_topic_url(tg_url)
        print(f"✅ Чат ID: {chat_id}, Топик ID: {thread_id}")
    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        return

    await bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text="👋 Привет! Это тестовое сообщение от твоего крутого скрипта."
    )



# === ФУНКЦИИ ===

def parse_telegram_topic_url(url):
    """
    Парсим ссылку вида https://t.me/c/CHAT_ID/THREAD_PARENT/THREAD_ID
    """
    match = re.match(r"https://t\.me/c/(-?\d+)/(\d+)(?:/(\d+))?", url)
    if not match:
        raise ValueError("Невалидная ссылка. Пример: https://t.me/c/1756893672/12759/12789")
    
    chat_id = int(f"-100{match.group(1)}")
    message_thread_id = int(match.group(2))
    return chat_id, message_thread_id

def transcode_m3u8(url, output_file):
    print(f"[*] Пережимаем: {url}")
    ffmpeg_command = [
        FFMPEG_PATH,
        "-i", url,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_file
    ]

    result = subprocess.run(ffmpeg_command)
    if result.returncode != 0:
        raise RuntimeError("FFmpeg зафейлился 😵")

def send_to_telegram(bot, chat_id, thread_id, video_path, caption=None):
    print("[*] Отправка в Телеграм...")
    with open(video_path, 'rb') as video:
        bot.send_video(
            chat_id=chat_id,
            video=video,
            supports_streaming=True,
            message_thread_id=thread_id,
            caption=caption,
            parse_mode=ParseMode.HTML
        )
    print("[+] Готово! 🎉")

# === ГЛАВНАЯ ===

def main2():
    bot = Bot(token=BOT_TOKEN)

    # 1. Получаем ссылку на тему в канале
    tg_url = input("Введи ссылку на тему в канале (вида https://t.me/c/...): ").strip()
    try:
        chat_id, thread_id = parse_telegram_topic_url(tg_url)
        print(f"✅ Чат ID: {chat_id}, Топик ID: {thread_id}")
    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        return

    print("\n🎬 Вводи m3u8 ссылки + заголовок (через пробел). Пиши `exit` чтобы выйти.")
    print("Примеры:")
    print("https://site.com/video.m3u8 Мой крутой заголовок")
    print("https://site.com/video2.m3u8\n")

    while True:
        line = input("👉 ").strip()
        if line.lower() in ["exit", "quit"]:
            break
        if not line:
            continue

        try:
            parts = line.split(maxsplit=1)
            url = parts[0]
            title = parts[1] if len(parts) > 1 else None

            transcode_m3u8(url, TEMP_FILE)
            send_to_telegram(bot, chat_id, thread_id, TEMP_FILE, caption=title)

        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            if os.path.exists(TEMP_FILE):
                os.remove(TEMP_FILE)
                print("[*] Временный файл удалён 🧹")


asyncio.run(main())