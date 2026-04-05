import requests
import os


def send_telegram_message(message, chat_id):

    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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

        if response.status_code != 200:
            print("Telegram response:", response.text)

    except Exception as e:
        print("❌ Telegram error:", e)