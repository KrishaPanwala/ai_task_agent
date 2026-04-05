# app/telegram_bot_runner.py
import os
from app.telegram_bot import application as telegram_app

async def start_telegram_bot_background():
    try:
        await telegram_app.initialize()
        await telegram_app.start()

        render_url = os.getenv("RENDER_EXTERNAL_URL")
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

        await telegram_app.bot.delete_webhook(drop_pending_updates=True)
        await telegram_app.bot.set_webhook(
            url=f"{render_url}/webhook/{bot_token}"
        )
        print("✅ Telegram webhook set successfully")
    except Exception as e:
        print("❌ Telegram bot error:", e)