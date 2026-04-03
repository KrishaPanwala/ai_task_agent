from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models import Task
from app.telegram_sender import send_telegram_message


def check_tasks():

    db = SessionLocal()

    tasks = db.query(Task).all()

    now = datetime.now(timezone.utc)

    for task in tasks:

        if task.time is None:
            continue

        task_time = task.time

        # convert to UTC if naive
        if task_time.tzinfo is None:
            task_time = task_time.replace(tzinfo=timezone.utc)

        if task_time <= now:

            send_telegram_message(
                f"⏰ Reminder\n{task.task}"
            )

            db.delete(task)
            db.commit()

    db.close()


def start_scheduler():

    scheduler = BackgroundScheduler()

    scheduler.add_job(
        check_tasks,
        "interval",
        seconds=30
    )

    scheduler.start()

    print("📅 Scheduler started")