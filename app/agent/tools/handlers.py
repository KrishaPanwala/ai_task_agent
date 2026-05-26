# app/agent/tools/handlers.py
"""
Each function here maps to a tool name in schemas.py.
They wrap your existing app functions so the agent can call them.
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.memory import get_memory as _get_memory, update_memory as _update_memory
from app.weather import is_outdoor_task, get_weather_for_time
from app.conflict import check_conflict, format_conflict_warning
from app.telegram import send_telegram_message
from app.db import SessionLocal
from app.models import Task, User

IST = ZoneInfo("Asia/Kolkata")


# ─── Memory ───────────────────────────────────────────────────────────────────

def read_memory(user_id: str) -> dict:
    """Return the user's memory profile as a dict the agent can reason over."""
    memory_text = _get_memory(int(user_id))
    return {
        "found": bool(memory_text),
        "profile": memory_text or "No memory yet. This is a new user.",
    }


def update_memory(user_id: str, updates: dict) -> dict:
    """
    Merge new observations into the user's memory profile.
    Calls your existing update_memory(user_id, task, time_str) under the hood,
    but accepts richer structured input from the agent.
    """
    notes = updates.get("notes", "")
    tasks = updates.get("frequent_tasks", [])
    times = updates.get("preferred_times", [])
    habits = updates.get("habits", {})

    # Build a summary string to append (your existing fn stores plain text)
    parts = []
    if tasks:
        parts.append(f"Frequent tasks: {', '.join(tasks)}")
    if times:
        parts.append(f"Preferred times: {', '.join(times)}")
    if habits:
        parts.append(f"Habits: {json.dumps(habits)}")
    if notes:
        parts.append(notes)

    summary = " | ".join(parts) if parts else "general update"
    _update_memory(int(user_id), summary, datetime.now(IST).strftime("%d %b %Y at %I:%M %p"))
    return {"status": "memory updated", "summary": summary}


# ─── Conflict ─────────────────────────────────────────────────────────────────

def check_conflicts(user_id: str, proposed_time: str, window_minutes: int = 15) -> dict:
    """Check for reminders within window_minutes of proposed_time."""
    try:
        parsed = datetime.fromisoformat(proposed_time)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=IST)
    except ValueError:
        return {"error": f"Could not parse datetime: {proposed_time}"}

    conflicts = check_conflict(int(user_id), parsed)
    warning = format_conflict_warning(conflicts)

    return {
        "has_conflicts": bool(conflicts),
        "count": len(conflicts),
        "warning": warning,
        "conflicts": [
            {
                "id": t.id,
                "task": t.task,
                "time": t.time.strftime("%d %b %Y at %I:%M %p"),
            }
            for t in conflicts
        ],
    }


# ─── Weather ──────────────────────────────────────────────────────────────────

def fetch_weather(latitude: float, longitude: float, datetime_str: str) -> dict:
    """Fetch weather forecast for the given coords and time."""
    try:
        parsed = datetime.fromisoformat(datetime_str)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=IST)
    except ValueError:
        return {"error": f"Could not parse datetime: {datetime_str}"}

    weather = get_weather_for_time(parsed)
    if not weather:
        return {"available": False, "message": "Weather data not available for this time."}

    return {
        "available": True,
        "description": weather["description"],
        "temperature": weather["temperature"],
        "rain_chance": weather["rain_chance"],
        "is_bad": weather["is_bad"],
        "summary": (
            f"{weather['description']}, {weather['temperature']}°C"
            + (f", {weather['rain_chance']}% rain chance" if weather["rain_chance"] > 0 else "")
            + (" — bad weather expected" if weather["is_bad"] else "")
        ),
    }


# ─── Save reminder ────────────────────────────────────────────────────────────

def save_reminder(
    user_id: str,
    task: str,
    scheduled_time: str,
    recurrence: str = "none",
    tags: list = None,
) -> dict:
    """Save a validated reminder to the database."""
    try:
        parsed = datetime.fromisoformat(scheduled_time)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=IST)
    except ValueError:
        return {"error": f"Could not parse scheduled_time: {scheduled_time}"}

    recur_map = {
        "daily": ("daily", None),
        "weekly": ("weekly", None),
        "hourly": ("hourly", None),
        "none": (None, None),
    }
    recur_type, recur_value = recur_map.get(recurrence, (None, None))

    db = SessionLocal()
    try:
        # Get chat_id for this user
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            return {"error": "User not found"}

        new_task = Task(
            task=task,
            time=parsed.replace(tzinfo=None),  # store naive (your existing pattern)
            chat_id=user.chat_id,
            user_id=int(user_id),
            is_recurring=recurrence != "none",
            recur_type=recur_type,
            recur_value=recur_value,
        )
        db.add(new_task)
        db.commit()
        task_id = new_task.id
    finally:
        db.close()

    return {
        "status": "saved",
        "task_id": task_id,
        "task": task,
        "scheduled_time": parsed.strftime("%d %b %Y at %I:%M %p"),
        "recurrence": recurrence,
    }


# ─── Goal decomposition ───────────────────────────────────────────────────────

def decompose_goal(user_id: str, goal: str, context: str = "") -> dict:
    """
    Ask the LLM to break a high-level goal into sub-reminders.
    Returns a list of {task, suggested_time, recurrence} dicts.
    The agent can then call save_reminder for each one after confirming with the user.
    """
    # This is handled inside the agent loop itself via a dedicated prompt —
    # we return a signal so the agent knows to do a planning pass.
    return {
        "action": "plan_goal",
        "goal": goal,
        "context": context,
        "user_id": user_id,
        "message": (
            "Goal received. The agent will now decompose this into sub-reminders "
            "and propose a schedule for user confirmation."
        ),
    }


# ─── Send message ─────────────────────────────────────────────────────────────

def send_message(user_id: str, message: str, reply_markup=None) -> dict:
    """Send a Telegram message to the user."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.chat_id:
            return {"error": "User has no chat_id linked"}
        chat_id = user.chat_id
    finally:
        db.close()

    try:
        send_telegram_message(message, chat_id)
        return {"status": "sent", "chat_id": chat_id}
    except Exception as e:
        return {"error": str(e)}


# ─── Dispatcher ───────────────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "read_memory": lambda args: read_memory(**args),
    "update_memory": lambda args: update_memory(**args),
    "check_conflicts": lambda args: check_conflicts(**args),
    "fetch_weather": lambda args: fetch_weather(**args),
    "save_reminder": lambda args: save_reminder(**args),
    "decompose_goal": lambda args: decompose_goal(**args),
    "send_message": lambda args: send_message(**args),
}


def dispatch_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a tool by name and return JSON string result."""
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = handler(tool_args)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})
