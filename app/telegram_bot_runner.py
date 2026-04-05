# app/telegram_bot_runner.py
import asyncio
from app.telegram_bot import application as telegram_app

async def start_telegram_bot_background():
    """Start telegram bot safely in existing event loop"""
    try:
        await telegram_app.initialize()
        await telegram_app.start()
        asyncio.create_task(telegram_app.updater.start_polling())
    except Exception as e:
        print("❌ Telegram bot error:", e)