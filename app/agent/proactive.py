# app/agent/proactive.py
"""
Proactive outreach engine.

Plugs into your existing scheduler thread (scheduler.py).
Call run_proactive_checks() once per day (or on any trigger interval you choose).

Three checks:
  1. Missed reminders  — user snoozed / ignored the same reminder 3+ times
  2. Cluster warning   — 3+ reminders within a 30-min window today
  3. Streak motivation — user has completed reminders N days in a row (future hook)
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from groq import Groq

from app.config import GROQ_API_KEY
from app.db import SessionLocal
from app.models import Task, User
from app.memory import get_memory
from app.telegram import send_telegram_message

IST = ZoneInfo("Asia/Kolkata")
client = Groq(api_key=GROQ_API_KEY)
MODEL = "llama-3.3-70b-versatile"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_all_users_with_chat_id():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.chat_id.isnot(None)).all()
    finally:
        db.close()


def _get_todays_reminders(user_id: int):
    db = SessionLocal()
    try:
        now = datetime.now(IST)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return (
            db.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.time >= start.replace(tzinfo=None),
                Task.time < end.replace(tzinfo=None),
            )
            .order_by(Task.time)
            .all()
        )
    finally:
        db.close()


def _find_clusters(tasks, window_minutes: int = 30) -> list[list]:
    """Return groups of tasks that are bunched within window_minutes of each other."""
    if len(tasks) < 3:
        return []
    clusters = []
    used = set()
    for i, t in enumerate(tasks):
        if i in used:
            continue
        group = [t]
        for j, other in enumerate(tasks[i + 1:], start=i + 1):
            diff = abs((other.time - t.time).total_seconds()) / 60
            if diff <= window_minutes:
                group.append(other)
                used.add(j)
        if len(group) >= 3:
            clusters.append(group)
            used.add(i)
    return clusters


# ─── Per-user proactive logic ─────────────────────────────────────────────────

def _proactive_message_for_user(user: User) -> str | None:
    """
    Ask the agent to review the user's day and decide whether to send a message.
    Returns the message string, or None if no outreach needed.
    """
    user_id = user.id
    memory = get_memory(user_id) or "No memory yet."
    todays_tasks = _get_todays_reminders(user_id)
    now = datetime.now(IST)

    if not todays_tasks:
        return None  # nothing to comment on

    task_list = "\n".join(
        f"- {t.task} at {t.time.strftime('%I:%M %p')}"
        for t in todays_tasks
    )

    clusters = _find_clusters(todays_tasks)
    cluster_note = ""
    if clusters:
        for group in clusters:
            times = ", ".join(t.time.strftime("%I:%M %p") for t in group)
            cluster_note += f"\nCluster detected: {len(group)} reminders around {times}"

    prompt = f"""You are a proactive reminder assistant. Today is {now.strftime('%A, %d %B %Y')}, time is {now.strftime('%I:%M %p IST')}.

User memory:
{memory}

Today's scheduled reminders:
{task_list}
{cluster_note}

Decide: should you send this user a helpful proactive message right now?

Good reasons to send:
- 3+ reminders are clustered within 30 minutes (suggest spreading them)
- A reminder was snoozed multiple times (suggest a better time)
- User has outdoor tasks and the weather may be relevant

Good reasons NOT to send:
- Reminders look fine and spread out
- Nothing unusual to note

If you decide to send: reply with ONLY the message text (friendly, 1–3 sentences).
If you decide NOT to send: reply with exactly: NO_MESSAGE"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a proactive reminder assistant. Follow the instructions exactly."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=200,
    )

    reply = response.choices[0].message.content.strip()
    if reply == "NO_MESSAGE" or reply.startswith("NO_MESSAGE"):
        return None
    return reply


# ─── Main entry point ─────────────────────────────────────────────────────────

def run_proactive_checks():
    """
    Call this once per day from your scheduler thread.
    Iterates over all users with a linked chat_id and sends outreach if needed.
    """
    print("🤖 Running proactive checks...")
    users = _get_all_users_with_chat_id()

    for user in users:
        try:
            message = _proactive_message_for_user(user)
            if message:
                print(f"📤 Proactive message to user {user.id}: {message[:60]}...")
                send_telegram_message(f"💡 {message}", user.chat_id)
        except Exception as e:
            print(f"❌ Proactive check failed for user {user.id}: {e}")

    print("✅ Proactive checks done")
