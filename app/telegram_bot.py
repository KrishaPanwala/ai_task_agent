# app/telegram_bot.py
import dateparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.config import TELEGRAM_BOT_TOKEN
from app.db import SessionLocal
from app.models import Task, User
from app.agent.loop import run_agent

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
        f"_Remind me to drink water at 5pm_\n"
        f"_Help me build a morning routine_",
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
        task_time = task.time.replace(tzinfo=IST)
        msg += f"🔹 *ID {task.id}* — {task.task}\n"
        msg += f"   ⏰ {task_time.strftime('%d %b %Y at %I:%M %p')}{recur_info}\n\n"

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

    try:
        if data.startswith("done_"):
            task_id = int(data.split("_")[1])
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                db.delete(task)
                db.commit()
            await query.edit_message_text("✅ Reminder marked as done!")

        elif data.startswith("snooze_"):
            # Format: snooze_{minutes}_{task_id}_{user_id}_{task_text}
            parts = data.split("_", 4)
            minutes     = int(parts[1])
            task_id     = int(parts[2])
            user_id_str = parts[3]
            task_text   = parts[4] if len(parts) > 4 else "Reminder"

            user_id  = int(user_id_str) if user_id_str != "none" else None
            new_time = datetime.now(IST) + timedelta(minutes=minutes)

            original = db.query(Task).filter(Task.id == task_id).first()
            chat_id  = original.chat_id if original else str(query.message.chat_id)

            if original:
                db.delete(original)

            new_task = Task(
                task=task_text,
                time=new_time.replace(tzinfo=None),
                chat_id=chat_id,
                user_id=user_id,
                is_recurring=False,
                recur_type=None,
                recur_value=None,
            )
            db.add(new_task)
            db.commit()

            await query.edit_message_text(
                f"⏰ Snoozed for {minutes} minute(s)!\n"
                f"New reminder at: {new_time.strftime('%d %b %Y at %I:%M %p')}"
            )

    except Exception as e:
        print(f"❌ Snooze error: {e}")
        await query.edit_message_text("❌ Something went wrong.")
    finally:
        db.close()


async def handle_message(update, context):
    """
    All natural language messages go through the ReAct agent loop.
    The agent handles memory, conflict check, weather, saving, and composes the reply.
    """
    user_message = update.message.text
    chat_id = update.message.chat_id

    # Look up user from chat_id
    db = SessionLocal()
    user = db.query(User).filter(User.chat_id == str(chat_id)).first()
    user_id = user.id if user else None
    db.close()

    if not user_id:
        await update.message.reply_text(
            "⚠️ Your Telegram account isn't linked yet.\n"
            "Please register at the web dashboard and paste your Chat ID."
        )
        return

    # Show typing indicator while agent thinks
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        reply = run_agent(user_message, user_id)
        await update.message.reply_text(reply)
    except Exception as e:
        if "429" in str(e):
            await update.message.reply_text("⏳ AI is busy right now, please try again in a few minutes.")
        else:
            print(f"❌ Agent error: {e}")
            await update.message.reply_text("❌ Something went wrong. Please try again.")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("list", list_tasks))
application.add_handler(CommandHandler("delete", delete_task))
application.add_handler(CommandHandler("clear", clear_tasks))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CallbackQueryHandler(handle_snooze))