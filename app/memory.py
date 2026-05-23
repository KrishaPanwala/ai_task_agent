# app/memory.py
from app.db import SessionLocal
from app.models import UserMemory
from datetime import datetime
from zoneinfo import ZoneInfo
from groq import Groq
from app.config import GROQ_API_KEY
import json

IST = ZoneInfo("Asia/Kolkata")
client = Groq(api_key=GROQ_API_KEY)

def get_memory(user_id: int) -> str:
    """Load user memory as a string to inject into AI prompt."""
    if not user_id:
        return ""
    db = SessionLocal()
    mem = db.query(UserMemory).filter(UserMemory.user_id == user_id).first()
    db.close()
    if not mem or not mem.memory:
        return ""
    return mem.memory

def update_memory(user_id: int, new_task: str, new_time: str):
    """After saving a reminder, update memory with new pattern."""
    if not user_id:
        return

    db = SessionLocal()
    mem = db.query(UserMemory).filter(UserMemory.user_id == user_id).first()
    existing = mem.memory if mem else ""

    prompt = f"""You are a memory manager for a reminder app.

Current memory about this user:
{existing if existing else "No memory yet."}

User just set a new reminder:
Task: {new_task}
Time: {new_time}

Update the memory to include useful patterns, habits, and preferences about this user.
Keep it short (max 10 lines). Focus on:
- Common reminder times (e.g. "usually sets morning reminders at 7am")
- Frequent tasks (e.g. "often reminded about water, medicine, meetings")
- Preferences (e.g. "prefers evening workouts")
- Any patterns you notice

Return ONLY the updated memory text, no explanation."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a concise memory manager. Return only the updated memory text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        updated_memory = response.choices[0].message.content.strip()

        if mem:
            mem.memory = updated_memory
            mem.updated_at = datetime.now(IST)
        else:
            mem = UserMemory(
                user_id=user_id,
                memory=updated_memory,
                updated_at=datetime.now(IST)
            )
            db.add(mem)

        db.commit()
        print(f"🧠 Memory updated for user {user_id}")
    except Exception as e:
        print(f"❌ Memory update error: {e}")
    finally:
        db.close()