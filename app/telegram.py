# app/telegram.py
import requests, os

def send_telegram_message(message, chat_id):
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN or not chat_id:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        response = requests.post(url, data={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"  # 👈 only line added
        })
        print(f"📤 Telegram response: {response.status_code} {response.text}")
    except Exception as e:
        print("❌ Telegram error:", e)