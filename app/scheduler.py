# app/scheduler.py
import threading, time, asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.db import SessionLocal
from app.models import Task
from app.telegram_bot import application as telegram_app

IST = ZoneInfo("Asia/Kolkata")

# ✅ Store the main event loop at startup
main_loop = None

def set_main_loop(loop):
    global main_loop
    main_loop = loop

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
                # ✅ Use main event loop instead of asyncio.run()
                asyncio.run_coroutine_threadsafe(
                    telegram_app.bot.send_message(
                        chat_id=task.chat_id,
                        text=f"🔔 *Reminder*\n\n📌 {task.task}",
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    ),
                    main_loop
                )
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