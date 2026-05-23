# app/telegram_bot.py
import dateparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.config import TELEGRAM_BOT_TOKEN
from app.ai import extract_task
from app.db import SessionLocal
from app.models import Task, User
from app.memory import get_memory, update_memory
from app.weather import is_outdoor_task, get_weather_for_time
from app.conflict import check_conflict, format_conflict_warning

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
        task_time = task.time.replace(tzinfo=IST)  # reattach IST after DB fetch
        msg += f"   ⏰ {task_time.strftime('%d %b %Y at %I:%M %p')}\n\n"

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
            # Try to delete if still exists (e.g. user taps Done before scheduler fires)
            task_id = int(data.split("_")[1])
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                db.delete(task)
                db.commit()
            await query.edit_message_text("✅ Reminder marked as done!")

        elif data.startswith("snooze_"):
            # Format: snooze_{minutes}_{task_id}_{user_id}_{task_text}
            parts = data.split("_", 4)  # max 5 parts, task text may have underscores
            minutes   = int(parts[1])
            task_id   = int(parts[2])
            user_id_str = parts[3]
            task_text = parts[4] if len(parts) > 4 else "Reminder"

            user_id = int(user_id_str) if user_id_str != "none" else None
            new_time = datetime.now(IST) + timedelta(minutes=minutes)

            # Try to get chat_id from original task (may still exist if user taps fast)
            original = db.query(Task).filter(Task.id == task_id).first()
            chat_id = original.chat_id if original else str(query.message.chat_id)

            # ✅ If original still exists in DB, delete it to avoid double firing
            if original:
                db.delete(original)

            # ✅ Create snoozed task with all fields intact
            new_task = Task(
                task=task_text,
                time=new_time.replace(tzinfo=None),
                chat_id=chat_id,
                user_id=user_id,        # ✅ web dashboard can see it
                is_recurring=False,
                recur_type=None,
                recur_value=None
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
    user_message = update.message.text
    chat_id = update.message.chat_id
    db = SessionLocal()
    user = db.query(User).filter(User.chat_id == str(chat_id)).first()
    user_id = user.id if user else None
    db.close()

    # 👇 load memory before AI call
    memory = get_memory(user_id) if user_id else ""

    result = extract_task(user_message, memory=memory)  # 👈 pass memory

    if "task" not in result or "time" not in result:
        await update.message.reply_text("❌ Could not understand task")
        return

    parsed_time = dateparser.parse(result["time"], settings={
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": "Asia/Kolkata",
        "TO_TIMEZONE": "Asia/Kolkata"
    })

    print(f"⏰ parsed_time: {parsed_time}")  # 👈 add this
    print(f"🕐 now IST: {datetime.now(IST)}")    
    
    if not parsed_time:
        await update.message.reply_text("❌ Invalid time")
        return
    
    # 👇 conflict check
    conflicts = check_conflict(user_id, parsed_time)
    conflict_warning = format_conflict_warning(conflicts)
    
    weather_warning = ""
    if is_outdoor_task(result["task"]):
        weather = get_weather_for_time(parsed_time)
        if weather:
            weather_warning = f"\n\n🌤️ Weather: {weather['description']}, {weather['temperature']}°C"
            if weather["rain_chance"] > 0:
                weather_warning += f", {weather['rain_chance']}% rain chance"
            if weather["is_bad"]:
                weather_warning += f"\n⚠️ Bad weather expected! Consider rescheduling."

    db = SessionLocal()

    user = db.query(User).filter(User.chat_id == str(chat_id)).first()
    user_id = user.id if user else None

    new_task = Task(
        task=result["task"],
        time=parsed_time.replace(tzinfo=None),
        chat_id=str(chat_id),
        user_id=user_id,
        is_recurring=result.get("is_recurring", False),
        recur_type=result.get("recur_type", None),
        recur_value=result.get("recur_value", None)
    )
    db.add(new_task)
    db.commit()
    db.close()

    # 👇 update memory after saving
    update_memory(user_id, result["task"], parsed_time.strftime("%d %b %Y at %I:%M %p"))

    recur_info = ""
    if result.get("is_recurring"):
        recur_info = f"\n🔁 Repeats: {result.get('recur_type')}"
        if result.get('recur_value'):
            recur_info += f" ({result.get('recur_value')})"

    await update.message.reply_text(
        f"✅ Task Added\n\n"
        f"📌 {result['task']}\n"
        f"⏰ {parsed_time.strftime('%d %b %Y at %I:%M %p')}"
        f"{recur_info}{weather_warning}{conflict_warning}"
    )

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("list", list_tasks))
application.add_handler(CommandHandler("delete", delete_task))
application.add_handler(CommandHandler("clear", clear_tasks))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CallbackQueryHandler(handle_snooze))