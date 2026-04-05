# app/scheduler.py
import threading, time
from datetime import datetime
from zoneinfo import ZoneInfo
from app.db import SessionLocal
from app.models import Task
from app.telegram import send_telegram_message

IST = ZoneInfo("Asia/Kolkata")

def check_tasks():
    print("⏰ Scheduler started")
    while True:
        try:
            db = SessionLocal()
            now = datetime.now(IST)  # ✅ now in IST
            tasks = db.query(Task).filter(Task.time <= now).all()
            for task in tasks:
                send_telegram_message(f"🔔 Reminder\n\n{task.task}", task.chat_id)
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