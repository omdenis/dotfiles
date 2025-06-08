import sys
import os
import re
import json
import subprocess
import argparse
import asyncio
from pathlib import Path
from telegram import Bot
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from datetime import datetime
from dotenv import load_dotenv

# sudo dnf install xfce4-screenshooter xdotool xclip

log_file = Path.home() / "tmp" / "telegram_screenshot.log"
(Path.home() / "tmp" ).mkdir(parents=True, exist_ok=True)

sys.stdout = open(log_file, "a")
sys.stderr = sys.stdout

load_dotenv(os.path.expanduser("~/.env"))
BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_ID = os.getenv("TELEGRAM_ID")
IMAGE_FILE = Path.home() / "tmp" /"screenshot.png"

CONFIG_PATH = Path.home() / ".config" / "tgsnap"
CONFIG_FILE = CONFIG_PATH / "config.json"
bot = Bot(token=BOT_TOKEN)

def main():    
    result = asyncio.run(handle_init())
    if result:
        return

    parser = argparse.ArgumentParser(description="Screenshot sender to Telegram")
    parser.add_argument("--init", action="store_true", help="Запуск с настройкой канала")
    args = parser.parse_args()

    if args.init:        
        try:
            chat_id, thread_id = parse_telegram_topic_url()        
            save_config(chat_id, thread_id)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return
     

    chat_id, thread_id = load_config()

    try:
        take_screenshot()
        asyncio.run(send_to_telegram(chat_id, thread_id))

    except Exception as e:
        print(f"❌ Ошибка: {e}")    

# === Обработка сообщений ===

async def handle_init():    
    print("[*] Получаем сообщения...")
    updates = await bot.get_updates(limit=100, allowed_updates=["message"])

    for update in reversed(updates):
        msg = update.message
        if not msg or not msg.text:
            continue

        text = msg.text.lower()
        user_id = str(msg.from_user.id)

        if user_id != TELEGRAM_ID:
            continue

        if "@init" in text:
            chat_id = msg.chat.id
            thread_id = msg.message_thread_id or (
                msg.reply_to_message.message_thread_id if msg.reply_to_message else None
            )

            if thread_id:
                print(f"[+] @init от {user_id}: chat={chat_id}, thread={thread_id}")                
                save_config(chat_id, thread_id)      
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
                    print(f"🗑️ Удалено сообщение @init от {user_id}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить сообщение: {e}")            
                await bot.get_updates(offset=update.update_id + 1)                  
                return True
            
    return False

def save_user_map(data):
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def save_config(chat_id, thread_id):
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"chat_id": chat_id, "thread_id": thread_id}, f)
    print(f"✅ Конфиг сохранён в {CONFIG_FILE}")

def load_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError("Конфиг не найден. Запусти скрипт с параметром --init")
    with open(CONFIG_FILE) as f:
        data = json.load(f)
    return data["chat_id"], data["thread_id"]

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
