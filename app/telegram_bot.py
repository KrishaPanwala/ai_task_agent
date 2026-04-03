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


# -------------------
# start command
# -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 AI Task Bot\n\nSend reminder like:\nremind me tomorrow 7pm to study"
    )


# -------------------
# handle message
# -------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    result = extract_task(text)

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
        f"✅ Task Added\n{result['task']}\n⏰ {parsed_time}"
    )


# -------------------
# start telegram bot
# -------------------
async def start_telegram_bot():

    app = ApplicationBuilder().token(
        TELEGRAM_BOT_TOKEN
    ).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("🤖 Telegram bot starting...")

    await app.initialize()
    await app.start()
    await app.bot.initialize()

    print("🤖 Telegram bot started successfully")