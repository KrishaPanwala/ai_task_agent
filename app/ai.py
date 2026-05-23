# app/ai.py
from groq import Groq
from app.config import GROQ_API_KEY
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
client = Groq(api_key=GROQ_API_KEY)

DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6
}

def get_first_occurrence(target_weekday: int, hour: int, minute: int) -> datetime:
    now = datetime.now(IST)
    days_ahead = target_weekday - now.weekday()
    if days_ahead < 0:
        days_ahead += 7
    elif days_ahead == 0 and (now.hour > hour or (now.hour == hour and now.minute >= minute)):
        days_ahead += 7
    first = now + timedelta(days=days_ahead)
    return first.replace(hour=hour, minute=minute, second=0, microsecond=0)

def extract_task(user_message: str) -> dict:
    now = datetime.now(IST)
    today_str = now.strftime("%A, %d %B %Y")
    current_time_str = now.strftime("%I:%M %p")

    prompt = f"""Today is {today_str}. Current time is {current_time_str} IST.

Extract task, time, and recurrence from: "{user_message}"

Return ONLY this JSON, no explanation, no markdown:
{{"task": "", "time": "", "is_recurring": false, "recur_type": null, "recur_value": null}}

Rules:
- "time" must ALWAYS be a full datetime in this exact format: "YYYY-MM-DD HH:MM" (24hr)
- If user mentions a SPECIFIC date (like "31st december", "june 20", "15th august"), use THAT exact date. Never change it.
- If no date mentioned, assume today. If time already passed today, use tomorrow.
- "every day/daily/everyday" → is_recurring=true, recur_type="daily"
- "every hour" → is_recurring=true, recur_type="hourly"
- "every X minutes" → is_recurring=true, recur_type="interval", recur_value="X"
- "every monday/tuesday/wednesday/thursday/friday/saturday/sunday" → is_recurring=true, recur_type="weekly", recur_value="<dayname lowercase>", time must be the NEXT upcoming <dayname> date
- No recurrence → is_recurring=false, recur_type=null, recur_value=null"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a JSON extractor. Return ONLY valid JSON. No explanation, no markdown, no extra text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        content = response.choices[0].message.content.strip()
        print("🤖 RAW AI:", content)

        content = re.sub(r'```json|```', '', content).strip()

        match = re.search(r'\{.*?\}', content, re.DOTALL)
        if not match:
            print(f"❌ No JSON found for: {user_message}")
            return {}

        data = json.loads(match.group().strip())

        if not data.get("task") or not data.get("time"):
            print(f"❌ Incomplete AI output: {data}")
            return {}

        # ✅ Safety net for weekly reminders — never trust Groq's date math
        if data.get("recur_type") == "weekly" and data.get("recur_value"):
            day_name = data["recur_value"].lower().strip()
            if day_name in DAY_MAP:
                try:
                    parsed = datetime.strptime(data["time"], "%Y-%m-%d %H:%M")
                    hour, minute = parsed.hour, parsed.minute
                except ValueError:
                    try:
                        parsed = datetime.strptime(data["time"], "%H:%M")
                        hour, minute = parsed.hour, parsed.minute
                    except ValueError:
                        print(f"❌ Could not parse time: {data['time']}")
                        return {}

                correct_dt = get_first_occurrence(DAY_MAP[day_name], hour, minute)
                data["time"] = correct_dt.strftime("%Y-%m-%d %H:%M")
                print(f"✅ Corrected weekly time to: {data['time']}")

        return data

    except Exception as e:
        print(f"❌ Groq error: {e} | message: {user_message}")
        return {}