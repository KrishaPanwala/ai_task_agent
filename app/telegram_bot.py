# app/telegram_bot.py
import dateparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.config import TELEGRAM_BOT_TOKEN
from app.ai import extract_task
from app.db import SessionLocal
from app.models import Task

IST = ZoneInfo("Asia/Kolkata")

application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

async def start(update, context):
    chat_id = update.message.chat_id
    await update.message.reply_text(
        f"🤖 *AI Reminder Bot Ready*\n\n"
        f"📌 *Your Chat ID:* `{chat_id}`\n\n"
        f"Copy this ID and paste it on the web dashboard!\n\n"
        f"*Commands:*\n"
        f"/list — show all pending reminders\n"
        f"/delete <id> — delete a reminder\n"
        f"/clear — delete all reminders\n\n"
        f"💬 Or just type naturally:\n"
        f"_Remind me to drink water at 5pm_",
        parse_mode="Markdown"
    )

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
        recur_info = f"\n   🔁 Repeats: {task.recur_type}" if task.is_recurring else ""
        msg += f"🔹 *ID {task.id}* — {task.task}\n"
        msg += f"   ⏰ {task.time.strftime('%d %b %Y at %I:%M %p')}{recur_info}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

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

async def handle_snooze(update, context):
    query = update.callback_query
    await query.answer()

    data = query.data
    db = SessionLocal()

    if data.startswith("done_"):
        await query.edit_message_text("✅ Reminder marked as done!")

    elif data.startswith("snooze_"):
        parts = data.split("_")
        minutes = int(parts[1])

        new_time = datetime.now(IST) + timedelta(minutes=minutes)
        task_text = query.message.text.split("📌 ")[-1].split("\n")[0].strip()

        new_task = Task(
            task=task_text,
            time=new_time,
            chat_id=str(query.message.chat_id),
            is_recurring=False
        )
        db.add(new_task)
        db.commit()
        await query.edit_message_text(
            f"⏰ Snoozed for {minutes} minute(s)!\n"
            f"New reminder at: {new_time.strftime('%d %b %Y at %I:%M %p')}"
        )

    db.close()

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

    # ✅ Find user by chat_id to link user_id
    from app.models import User
    user = db.query(User).filter(User.chat_id == str(chat_id)).first()
    user_id = user.id if user else None

    new_task = Task(
        task=result["task"],
        time=parsed_time,
        chat_id=str(chat_id),
        user_id=user_id,  # ✅ link to web user
        is_recurring=result.get("is_recurring", False),
        recur_type=result.get("recur_type", None),
        recur_value=result.get("recur_value", None)
    )
    db.add(new_task)
    db.commit()
    db.close()

    recur_info = ""
    if result.get("is_recurring"):
        recur_info = f"\n🔁 Repeats: {result.get('recur_type')}"
        if result.get('recur_value'):
            recur_info += f" ({result.get('recur_value')})"

    await update.message.reply_text(
        f"✅ Task Added\n\n"
        f"📌 {result['task']}\n"
        f"⏰ {parsed_time.strftime('%d %b %Y at %I:%M %p')}"
        f"{recur_info}"
    )

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("list", list_tasks))
application.add_handler(CommandHandler("delete", delete_task))
application.add_handler(CommandHandler("clear", clear_tasks))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CallbackQueryHandler(handle_snooze))