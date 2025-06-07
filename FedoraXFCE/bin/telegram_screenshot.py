import os
import re
import json
import subprocess
import asyncio
from pathlib import Path
from telegram import Bot
from datetime import datetime
from dotenv import load_dotenv

# sudo dnf install xfce4-screenshooter xdotool xclip

load_dotenv(os.path.expanduser("~/.env"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

REGION_FILE = "/home/denis/.config/ss_region.json"
IMAGE_FILE = "/tmp/screenshot.png"

def main():    
    chat_id, thread_id = parse_telegram_topic_url()        

    while True:
        line = input("👉 ").strip()
        if line.lower() in ["exit", "quit"]:
            break

        try:
           take_screenshot()
           asyncio.run(send_to_telegram(chat_id, thread_id))

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            continue


# === СКРИНШОТ X11 (XFCE)

def take_screenshot():
    print("[*] Выбор региона скриншота через xfce4-screenshooter...")
    if Path(IMAGE_FILE).exists():
        os.remove(IMAGE_FILE)

    subprocess.run([
        "xfce4-screenshooter",
        "--region",
        "--save", IMAGE_FILE
    ])
    if not Path(IMAGE_FILE).exists():
        raise RuntimeError("❌ Скриншот не был сохранён!")

# === ТЕЛЕГРАМ ===

async def send_to_telegram(chat_id, thread_id):
    print("[*] Отправка скрина в Telegram...")
    bot = Bot(token=BOT_TOKEN)
    with open(IMAGE_FILE, "rb") as img:
        await bot.send_photo(
            chat_id=chat_id,
            photo=img,
            message_thread_id=thread_id,
            # caption=f"🖼️ Скриншот {datetime.now().strftime('%H:%M:%S')}" - добавить заголовок текущей закладки приложения
        )
    print("✅ Отправлено!")


def parse_telegram_topic_url():
    """
        Парсим ссылку вида https://t.me/c/CHAT_ID/THREAD_ID/MSG_ID
    """
    tg_url = input("Введи ссылку на тему в канале (вида https://t.me/c/...): ").strip()
    match = re.match(r"https://t\.me/c/(-?\d+)/(\d+)(?:/(\d+))?", tg_url)
    if not match:
        raise ValueError("Невалидная ссылка. Пример: https://t.me/c/1756893672/12759/12789")
    
    chat_id = int(f"-100{match.group(1)}")
    thread_id = int(match.group(2))
    print(f"✅ Чат ID: {chat_id}, Топик ID: {thread_id}")
    return chat_id, thread_id

if __name__ == "__main__":
    main()
