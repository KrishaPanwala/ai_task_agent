# app/telegram_bot.py
import dateparser
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from app.config import TELEGRAM_BOT_TOKEN
from app.ai import extract_task
from app.db import SessionLocal
from app.models import Task

application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

async def start(update, context):
    await update.message.reply_text("🤖 AI Reminder Bot Ready")

async def handle_message(update, context):
    user_message = update.message.text
    chat_id = update.message.chat_id

    result = extract_task(user_message)
    if "task" not in result or "time" not in result:
        await update.message.reply_text("❌ Could not understand task")
        return

    parsed_time = dateparser.parse(result["time"], settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": True})
    if not parsed_time:
        await update.message.reply_text("❌ Invalid time")
        return

    db = SessionLocal()
    new_task = Task(task=result["task"], time=parsed_time, chat_id=str(chat_id))
    db.add(new_task)
    db.commit()
    db.close()

    await update.message.reply_text(f"✅ Task Added\n\n{result['task']}")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ✅ NO run_polling() here — that was the bug