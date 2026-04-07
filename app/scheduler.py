# app/scheduler.py
import threading, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import asyncio
from app.db import SessionLocal
from app.models import Task
from app.telegram_bot import application as telegram_app

IST = ZoneInfo("Asia/Kolkata")

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
                asyncio.run(telegram_app.bot.send_message(
                    chat_id=task.chat_id,
                    text=f"🔔 *Reminder*\n\n📌 {task.task}",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                ))
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