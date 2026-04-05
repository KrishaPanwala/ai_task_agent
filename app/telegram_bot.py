from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from app.ai import extract_task
from app.db import SessionLocal
from app.models import Task
from app.config import TELEGRAM_BOT_TOKEN

import dateparser
from datetime import timezone
import asyncio


# -------------------------
# START COMMAND
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 AI Reminder Bot\n\n"
        "Send message like:\n"
        "remind me tomorrow 7pm to study"
    )


# -------------------------
# HANDLE MESSAGE
# -------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_message = update.message.text
    chat_id = update.message.chat_id

    print("📩 Telegram message:", user_message)

    result = extract_task(user_message)

    print("🧠 AI result:", result)

    if "task" not in result or "time" not in result:
        await update.message.reply_text(
            "❌ Could not understand task"
        )
        return

    parsed_time = dateparser.parse(
        result["time"],
        settings={
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": True
        }
    )

    if not parsed_time:
        await update.message.reply_text(
            "❌ Invalid time"
        )
        return

    parsed_time = parsed_time.astimezone(timezone.utc)

    db = SessionLocal()

    new_task = Task(
        task=result["task"],
        time=parsed_time,
        chat_id=str(chat_id)
    )

    db.add(new_task)
    db.commit()
    db.close()

    await update.message.reply_text(
        f"✅ Task Added\n\n"
        f"{result['task']}\n"
        f"⏰ {parsed_time}"
    )


# -------------------------
# START TELEGRAM BOT
# -------------------------
async def start_telegram_bot():

    application = ApplicationBuilder().token(
        TELEGRAM_BOT_TOKEN
    ).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("🤖 Telegram bot starting...")

    await application.initialize()

    await application.bot.delete_webhook(
        drop_pending_updates=True
    )

    await application.run_polling()

    print("🤖 Telegram bot starting...")

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    print("🤖 Telegram bot started successfully")