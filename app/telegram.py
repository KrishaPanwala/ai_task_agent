import requests
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def send_telegram_message(message, chat_id):

    if not TOKEN or not chat_id:
        print("Telegram token or chat_id missing")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": message
    }

    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram send error:", e)