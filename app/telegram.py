import requests
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_telegram_message(message):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": int(TELEGRAM_CHAT_ID),
        "text": message
    }

    try:
        response = requests.post(
            url,
            data=data,
            timeout=10
        )

        if response.status_code != 200:
            print("Telegram error:", response.text)

    except Exception as e:
        print("Telegram request failed:", e)