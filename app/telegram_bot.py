# app/telegram_bot.py
import dateparser
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.config import TELEGRAM_BOT_TOKEN
from app.ai import extract_task
from app.db import SessionLocal
from app.models import Task
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

async def start(update, context):
    await update.message.reply_text(
        "🤖 *AI Reminder Bot Ready*\n\n"
        "📌 *Commands:*\n"
        "/list — show all pending reminders\n"
        "/delete <id> — delete a reminder\n"
        "/clear — delete all reminders\n\n"
        "💬 Or just type naturally:\n"
        "_Remind me to drink water at 5pm_",
        parse_mode="Markdown"
    )

# ✅ /list command
async def list_tasks(update, context):
    chat_id = str(update.message.chat_id)
    db = SessionLocal()
    tasks = db.query(Task).filter(Task.chat_id == chat_id).all()
    db.close()

    if not tasks:
        await update.message.reply_text("📭 No pending reminders!")
        return

    msg = "📋 *Your Pending Reminders:*\n\n"
    for task in tasks:
        msg += f"🔹 *ID {task.id}* — {task.task}\n"
        msg += f"   ⏰ {task.time.strftime('%d %b %Y at %I:%M %p')}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ✅ /delete <id> command
async def delete_task(update, context):
    chat_id = str(update.message.chat_id)
    if not context.args:
        await update.message.reply_text("❌ Usage: /delete <id>\nExample: /delete 3")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Usage: /delete 3")
        return

    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id, Task.chat_id == chat_id).first()
    if task:
        db.delete(task)
        db.commit()
        await update.message.reply_text(f"✅ Deleted: *{task.task}*", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Task not found or not yours!")
    db.close()

# ✅ /clear command
async def clear_tasks(update, context):
    chat_id = str(update.message.chat_id)
    db = SessionLocal()
    tasks = db.query(Task).filter(Task.chat_id == chat_id).all()
    count = len(tasks)
    for task in tasks:
        db.delete(task)
    db.commit()
    db.close()
    await update.message.reply_text(f"🗑️ Cleared *{count}* reminder(s)!", parse_mode="Markdown")

async def handle_message(update, context):
    user_message = update.message.text
    chat_id = update.message.chat_id

    result = extract_task(user_message)
    if "task" not in result or "time" not in result:
        await update.message.reply_text("❌ Could not understand task")
        return

    parsed_time = dateparser.parse(result["time"], settings={
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": "Asia/Kolkata",
        "TO_TIMEZONE": "Asia/Kolkata"
    })
    if not parsed_time:
        await update.message.reply_text("❌ Invalid time")
        return

    db = SessionLocal()
    new_task = Task(task=result["task"], time=parsed_time, chat_id=str(chat_id))
    db.add(new_task)
    db.commit()
    db.close()

    await update.message.reply_text(
        f"✅ Task Added\n\n"
        f"📌 {result['task']}\n"
        f"⏰ {parsed_time.strftime('%d %b %Y at %I:%M %p')}"
    )

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("list", list_tasks))
application.add_handler(CommandHandler("delete", delete_task))
application.add_handler(CommandHandler("clear", clear_tasks))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))