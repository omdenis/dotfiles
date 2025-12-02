#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Screenshot → Telegram with safe config mode for Fedora (Wayland/X11).
- Config mode: python telegram_screenshot.py "https://t.me/c/<CHAT>/<THREAD>[/<MSG>]"
  Only parses URL and writes ~/.config/tgsnap/config.json, then exits.
- Normal mode: python telegram_screenshot.py
  Takes a region screenshot and sends it to a Telegram topic.

Fedora deps:
  Wayland path:   sudo dnf install gnome-screenshot wl-clipboard
  (alt Wayland):  sudo dnf install grim slurp
  X11 path:       sudo dnf install xfce4-screenshooter xclip
"""

import os
import re
import json
import argparse
import asyncio
import logging
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# -------------------- Paths & logging --------------------
HOME = Path.home()
TMP_DIR = HOME / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = TMP_DIR / "telegram_screenshot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ],
)
log = logging.getLogger("tgsnap")

# -------------------- Config paths -----------------------
CONFIG_PATH = HOME / ".config" / "tgsnap"
CONFIG_FILE = CONFIG_PATH / "config.json"
IMAGE_FILE = TMP_DIR / "screenshot.png"

# -------------------- Env -------------------------------
# NOTE: we load .env early, but we DO NOT touch Telegram client in config-mode.
load_dotenv(os.path.expanduser("~/.env"))
BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_ID = os.getenv("TELEGRAM_ID")  # not used now, kept for future


# ==================== Utils =============================
def is_wayland() -> bool:
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def run_cmd(cmd, timeout=60, **popen_kwargs):
    """
    Safe runner with timeout and check=True.
    Returns CompletedProcess.
    """
    log.debug("RUN: %s", " ".join(map(str, cmd)))
    return subprocess.run(cmd, check=True, timeout=timeout, **popen_kwargs)


def copy_to_clipboard(text: str):
    """
    Copy text to clipboard using wl-copy (Wayland) or xclip (X11).
    """
    try:
        if is_wayland() and shutil.which("wl-copy"):
            run_cmd(["wl-copy"], input=text.encode("utf-8"), timeout=5)
        elif shutil.which("xclip"):
            run_cmd(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), timeout=5)
        else:
            raise RuntimeError("No clipboard tool found (need wl-copy or xclip).")
        log.info("📋 Link copied to clipboard")
    except Exception as e:
        log.warning("⚠️ Clipboard copy failed: %s", e)


# ================= Screenshot ===========================
def take_screenshot():
    """
    Region screenshot saved to IMAGE_FILE.
    Picks tools based on session type, with timeouts and fallbacks.
    """
    log.info("[*] Selecting screenshot region...")
    if IMAGE_FILE.exists():
        try:
            IMAGE_FILE.unlink()
        except Exception as e:
            log.warning("Could not remove previous image: %s", e)

    if is_wayland():
        # Prefer GNOME Screenshot (uses portal, friendly on Fedora GNOME)
        if shutil.which("gnome-screenshot"):
            # -a = area select, -f = output file
            run_cmd(["gnome-screenshot", "-a", "-f", str(IMAGE_FILE)], timeout=120)
        elif shutil.which("grim") and shutil.which("slurp"):
            # slurp prints geometry, grim captures
            geom = subprocess.check_output(["slurp"]).decode().strip()
            run_cmd(["grim", "-g", geom, str(IMAGE_FILE)], timeout=120)
        else:
            raise RuntimeError(
                "Wayland session detected but neither gnome-screenshot nor grim+slurp found.\n"
                "Install with: sudo dnf install gnome-screenshot  (or grim slurp)"
            )
    else:
        # X11 path
        if shutil.which("xfce4-screenshooter"):
            run_cmd(["xfce4-screenshooter", "--region", "--save", str(IMAGE_FILE)], timeout=120)
        else:
            raise RuntimeError(
                "X11 session detected but xfce4-screenshooter not found.\n"
                "Install with: sudo dnf install xfce4-screenshooter"
            )

    if not IMAGE_FILE.exists():
        raise RuntimeError("❌ Screenshot not saved!")


# ================= Telegram =============================
async def send_to_telegram(chat_id: int, thread_id: int):
    """
    Lazy-import and lazy-create the Telegram Bot.
    Only called in normal mode (never in config mode).
    """
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set in ~/.env")

    # Lazy import to avoid touching telegram libs in config mode
    from telegram import Bot

    bot = Bot(token=BOT_TOKEN)

    log.info("[*] Sending screenshot to Telegram...")
    with open(IMAGE_FILE, "rb") as img:
        msg = await bot.send_photo(
            chat_id=chat_id,
            photo=img,
            message_thread_id=thread_id,
        )
    log.info("✅ Sent")

    # Build URL to the message in topic
    chat_id_str = str(chat_id).replace("-100", "")
    msg_url = f"https://t.me/c/{chat_id_str}/{thread_id}/{msg.message_id}"
    log.info("🔗 Message URL: %s", msg_url)

    copy_to_clipboard(msg_url)


async def send_test_message(chat_id: int, thread_id: int):
    """
    Send a test message "." to verify the configuration is correct.
    """
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set in ~/.env")

    # Lazy import to avoid touching telegram libs when not needed
    from telegram import Bot

    bot = Bot(token=BOT_TOKEN)

    log.info("[*] Sending test message to verify configuration...")
    await bot.send_message(
        chat_id=chat_id,
        text=".",
        message_thread_id=thread_id,
    )
    log.info("✅ Test message sent successfully")


# ================= Config helpers =======================
def save_config(chat_id: int, thread_id: int):
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"chat_id": chat_id, "thread_id": thread_id}, f, ensure_ascii=False, indent=2)
    log.info("✅ Config saved to %s", CONFIG_FILE)


def load_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            "Config not found. Run with a Telegram topic link first, e.g.:\n"
            '  python telegram_screenshot.py "https://t.me/c/1756893672/12759"'
        )
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return int(data["chat_id"]), int(data["thread_id"])


def parse_telegram_topic_url(tg_url: str):
    """
    Accepts:
      https://t.me/c/CHAT_ID/THREAD_ID
      https://t.me/c/CHAT_ID/THREAD_ID/MSG_ID (MSG is ignored here)
    Returns (chat_id_with_minus_100_prefix, thread_id)
    """
    tg_url = tg_url.strip()
    match = re.match(r"^https://t\.me/c/(-?\d+)/(\d+)(?:/(\d+))?$", tg_url)
    if not match:
        raise ValueError("Invalid link. Example: https://t.me/c/1756893672/12759/12789")

    # Telegram supergroup internal id has -100 prefix
    chat_id = int(f"-100{match.group(1)}")
    thread_id = int(match.group(2))
    log.info("✅ Parsed: chat_id=%s, thread_id=%s", chat_id, thread_id)
    return chat_id, thread_id


# ================= Entry point ==========================
def main():
    parser = argparse.ArgumentParser(
        description=(
            "Screenshot sender to Telegram.\n"
            "Call with a Telegram topic link to (re)configure; "
            "no link = just send screenshot."
        )
    )
    parser.add_argument(
        "link",
        nargs="?",
        help="Link to topic/message like https://t.me/c/<CHAT>/<THREAD>[/<MSG>]"
    )
    args = parser.parse_args()

    # --------- CONFIG MODE: do nothing heavy, then exit ---------
    if args.link:
        try:
            chat_id, thread_id = parse_telegram_topic_url(args.link)
            save_config(chat_id, thread_id)
            log.info("[%s] ✅ Reconfigured: chat_id=%s, thread_id=%s",
                     datetime.now().isoformat(timespec="seconds"), chat_id, thread_id)
            # Send test message to verify configuration
            asyncio.run(send_test_message(chat_id, thread_id))
        except Exception as e:
            log.exception("❌ URL parse error: %s", e)
        return  # VERY IMPORTANT: exit immediately; don't touch telegram libs, etc.

    # --------- NORMAL MODE: read config, screenshot, send ---------
    try:
        chat_id, thread_id = load_config()
    except Exception as e:
        log.error("❌ Config read error: %s", e)
        return

    try:
        take_screenshot()
        asyncio.run(send_to_telegram(chat_id, thread_id))
    except Exception as e:
        log.exception("❌ Failure: %s", e)


if __name__ == "__main__":
    main()
