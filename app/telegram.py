import requests
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def send_telegram_message(message, chat_id):

    if not TOKEN:
        print("❌ Telegram token missing")
        return

    if not chat_id:
        print("❌ Chat ID missing")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": message
    }

    try:
        response = requests.post(url, data=data)

        print("📤 Telegram sent:", response.status_code)

    except Exception as e:
        print("❌ Telegram error:", e)