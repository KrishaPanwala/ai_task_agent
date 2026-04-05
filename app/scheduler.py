import time
import threading
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models import Task
from app.telegram import send_telegram_message


def check_tasks():

    print("⏰ Scheduler started")

    while True:

        try:
            db = SessionLocal()

            now = datetime.now(timezone.utc)

            tasks = db.query(Task).filter(
                Task.time <= now
            ).all()

            for task in tasks:

                print(
                    f"🕒 Task: {task.task} | Chat: {task.chat_id}"
                )

                print(
                    f"🔔 Sending reminder: {task.task}"
                )

                send_telegram_message(
                    f"🔔 Reminder\n\n{task.task}",
                    task.chat_id
                )

                db.delete(task)
                db.commit()

                print("✅ Task completed and deleted")

            db.close()

        except Exception as e:
            print("❌ Scheduler error:", e)

        time.sleep(10)


def start_scheduler():

    thread = threading.Thread(
        target=check_tasks,
        daemon=True
    )

    thread.start()

    print("✅ Scheduler thread started")