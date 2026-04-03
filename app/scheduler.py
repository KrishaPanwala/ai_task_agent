from apscheduler.schedulers.background import BackgroundScheduler
from app.telegram import send_telegram_message
from app.db import SessionLocal
from app.models import Task
from datetime import datetime, timezone

scheduler = BackgroundScheduler()


def check_tasks():

    db = SessionLocal()

    try:
        tasks = db.query(Task).all()
        now = datetime.now(timezone.utc)

        for task in tasks:

            if task.time <= now:

                send_telegram_message(
                    f"🔔 Reminder\n{task.task}"
                )

                db.delete(task)
                db.commit()

    finally:
        db.close()


def start_scheduler():

    if scheduler.running:
        return

    scheduler.add_job(
        check_tasks,
        "interval",
        seconds=30
    )

    scheduler.start()