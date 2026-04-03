from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from app.ai import extract_task
from app.db import SessionLocal
from app.models import Task
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

import dateparser
import requests


# -----------------------------
# Send Telegram Message
# -----------------------------
def send_telegram_message(message):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    requests.post(url, data=data)


# -----------------------------
# Start Command
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 AI Task Bot\nSend me a reminder like:\nremind me tomorrow 7pm to study"
    )


# -----------------------------
# Handle Messages
# -----------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_message = update.message.text

    result = extract_task(user_message)

    if "task" not in result or "time" not in result:
        await update.message.reply_text("❌ Could not understand task")
        return

    parsed_time = dateparser.parse(
        result["time"],
        settings={"PREFER_DATES_FROM": "future"}
    )

    if not parsed_time:
        await update.message.reply_text("❌ Invalid time")
        return

    db = SessionLocal()

    new_task = Task(
        task=result["task"],
        time=parsed_time
    )

    db.add(new_task)
    db.commit()
    db.close()

    await update.message.reply_text(
        f"✅ Task Added\n\n{result['task']}\n⏰ {parsed_time}"
    )


# -----------------------------
# Start Telegram Bot
# -----------------------------
async def start_telegram_bot():

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Telegram bot started")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()