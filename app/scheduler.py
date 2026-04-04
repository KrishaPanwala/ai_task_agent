import time
import threading
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models import Task
from app.telegram import send_telegram_message


def check_tasks():

    print("⏰ Scheduler started")

    while True:

        db = SessionLocal()

        tasks = db.query(Task).all()

        now = datetime.now(timezone.utc)

        for task in tasks:

            task_time = task.time

            if task_time.tzinfo is None:
                task_time = task_time.replace(tzinfo=timezone.utc)

            diff = (task_time - now).total_seconds()

            if 0 <= diff <= 30:

                print("🔔 Sending reminder:", task.task)

                send_telegram_message(
                    f"🔔 Reminder\n\n{task.task}",
                    task.chat_id
                )

                db.delete(task)
                db.commit()

        db.close()

        time.sleep(10)


def start_scheduler():

    thread = threading.Thread(
        target=check_tasks,
        daemon=True
    )

    thread.start()