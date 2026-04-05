import time
import threading
from datetime import datetime, timezone
from app.db import SessionLocal
from app.models import Task
from app.telegram import send_telegram_message

def check_tasks():
    print("⏰ Scheduler started")
    while True:
        db = None
        try:
            db = SessionLocal()
            now = datetime.now(timezone.utc)
            tasks = db.query(Task).filter(Task.time <= now).all()
            for task in tasks:
                print(f"🕒 Task: {task.task} | Chat: {task.chat_id}")
                send_telegram_message(f"🔔 Reminder\n📌 {task.task}", task.chat_id)
                db.delete(task)
                db.commit()
        except Exception as e:
            print("❌ Scheduler error:", e)
        finally:
            if db:
                db.close()
        time.sleep(10)

def start_scheduler():
    thread = threading.Thread(target=check_tasks, daemon=True)
    thread.start()
    print("✅ Scheduler thread started")