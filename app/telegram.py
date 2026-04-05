import requests
import os
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(message, chat_id=None):
    if not chat_id:
        chat_id = TELEGRAM_CHAT_ID

    if not TELEGRAM_BOT_TOKEN or not chat_id:
        print("❌ Missing token or chat_id")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": message}

    try:
        response = requests.post(url, data=data, timeout=10)
        print("📤 Telegram sent:", response.status_code)
        if response.status_code != 200:
            print("Telegram response:", response.text)
    except Exception as e:
        print("❌ Telegram error:", e)