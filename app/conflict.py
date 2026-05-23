# app/conflict.py
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.db import SessionLocal
from app.models import Task

IST = ZoneInfo("Asia/Kolkata")

def check_conflict(user_id: int, new_time: datetime, window_minutes: int = 15) -> list:
    """
    Check if any existing reminders overlap within window_minutes of new_time.
    Returns list of conflicting tasks.
    """
    if not user_id:
        return []

    new_time_naive = new_time.replace(tzinfo=None)
    window_start = new_time_naive - timedelta(minutes=window_minutes)
    window_end = new_time_naive + timedelta(minutes=window_minutes)

    db = SessionLocal()
    conflicts = db.query(Task).filter(
        Task.user_id == user_id,
        Task.time >= window_start,
        Task.time <= window_end
    ).all()
    db.close()

    return conflicts

def format_conflict_warning(conflicts: list) -> str:
    """Format conflict warning message."""
    if not conflicts:
        return ""

    warning = f"\n\n⚠️ *Conflict detected!* You have {len(conflicts)} nearby reminder(s):\n"
    for c in conflicts:
        task_time = c.time.replace(tzinfo=IST)
        warning += f"• {c.task} at {task_time.strftime('%I:%M %p')}\n"
    warning += "Consider rescheduling to avoid overlap."
    return warning