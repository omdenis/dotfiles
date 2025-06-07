import asyncio
import subprocess
import os
import re
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv

# https://t.me/c/2019239319/3442/5264
CHAT_ID = -1002019239319
THREAD_ID = 3442

async def main():
    load_dotenv(os.path.expanduser("~/.env"))
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(
        chat_id=CHAT_ID,
        message_thread_id=THREAD_ID,
        text="👋 Привет! Это тестовое сообщение от твоего крутого скрипта."
    )

asyncio.run(main())

