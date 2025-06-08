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

load_dotenv(os.path.expanduser("~/.env"))
BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_ID = os.getenv("TELEGRAM_ID")

CONFIG_PATH = Path.home() / ".config" / "tgvideo"
CONFIG_FILE = CONFIG_PATH / "config.json"
bot = Bot(token=BOT_TOKEN)

def main():    
    init();
    asyncio.run(handle_init())
    


def init():
    log_file = Path.home() / "tmp" / "telegram_video.log"
    (Path.home() / "tmp" ).mkdir(parents=True, exist_ok=True)
    sys.stdout = open(log_file, "a")
    sys.stderr = sys.stdout


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

        if "@video" in text:
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

if __name__ == "__main__":
    main()
