# app/scheduler.py
import threading, time, asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.db import SessionLocal
from app.models import Task
from app.telegram_bot import application as telegram_app

IST = ZoneInfo("Asia/Kolkata")
main_loop = None

def set_main_loop(loop):
    global main_loop
    main_loop = loop

def next_recur_time(task):
    now = datetime.now(IST)
    if task.recur_type == "daily":
        # Same time tomorrow
        return task.time + timedelta(days=1)
    elif task.recur_type == "hourly":
        return task.time + timedelta(hours=1)
    elif task.recur_type == "interval":
        minutes = int(task.recur_value)
        return task.time + timedelta(minutes=minutes)
    elif task.recur_type == "weekly":
        return task.time + timedelta(weeks=1)
    return None

def check_tasks():
    print("⏰ Scheduler started")
    while True:
        try:
            db = SessionLocal()
            now = datetime.now(IST)
            tasks = db.query(Task).filter(Task.time <= now).all()
            for task in tasks:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Done", callback_data=f"done_{task.id}"),
                        InlineKeyboardButton("⏰ 10 min", callback_data=f"snooze_10_{task.id}"),
                        InlineKeyboardButton("⏰ 1 hr", callback_data=f"snooze_60_{task.id}"),
                    ]
                ])

                # ✅ Add recurring label
                recur_label = ""
                if task.is_recurring:
                    recur_label = f"\n🔁 Recurring: {task.recur_type}"

                asyncio.run_coroutine_threadsafe(
                    telegram_app.bot.send_message(
                        chat_id=task.chat_id,
                        text=f"🔔 *Reminder*\n\n📌 {task.task}{recur_label}",
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    ),
                    main_loop
                )

                # ✅ If recurring, create next occurrence instead of deleting
                if task.is_recurring:
                    next_time = next_recur_time(task)
                    if next_time:
                        new_task = Task(
                            task=task.task,
                            time=next_time,
                            chat_id=task.chat_id,
                            is_recurring=True,
                            recur_type=task.recur_type,
                            recur_value=task.recur_value
                        )
                        db.add(new_task)

                db.delete(task)
                db.commit()
            db.close()
        except Exception as e:
            print("❌ Scheduler error:", e)
        time.sleep(10)

def start_scheduler():
    thread = threading.Thread(target=check_tasks, daemon=True)
    thread.start()
    print("✅ Scheduler thread started")