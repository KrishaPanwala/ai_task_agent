from apscheduler.schedulers.background import BackgroundScheduler
from app.telegram import send_telegram_message
from app.db import SessionLocal
from app.models import Task
from datetime import datetime

scheduler = BackgroundScheduler()


def check_tasks():

    db = SessionLocal()

    tasks = db.query(Task).all()

    now = datetime.now()

    for task in tasks:

        if task.time <= now:

            send_telegram_message(
                f"🔔 Reminder\nTask: {task.task}\nTime: {task.time.strftime('%I:%M %p')}"
            )

            db.delete(task)
            db.commit()

    db.close()


def start_scheduler():
    scheduler.add_job(check_tasks, "interval", seconds=30)
    scheduler.start()