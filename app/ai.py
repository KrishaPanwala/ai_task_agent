# app/ai.py
from groq import Groq
from app.config import GROQ_API_KEY
import json
import re

client = Groq(api_key=GROQ_API_KEY)

def extract_task(user_message: str) -> dict:
    prompt = f"""
    Extract task, time, and recurrence from this message.

    Message: {user_message}

    Rules:
    - If message says "every day" or "daily" → recur_type = "daily"
    - If message says "every hour" → recur_type = "hourly"
    - If message says "every X minutes" → recur_type = "interval", recur_value = X (in minutes)
    - If message says "every monday/tuesday/etc" → recur_type = "weekly", recur_value = "monday"
    - If no recurrence → is_recurring = false, recur_type = null, recur_value = null
    - time should be the first occurrence time (e.g. "8am", "tomorrow 6pm")

    Return only JSON:
    {{
        "task": "",
        "time": "",
        "is_recurring": false,
        "recur_type": null,
        "recur_value": null
    }}
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You extract task, time and recurrence info from reminder messages. Always return valid JSON only."},
                {"role": "user", "content": prompt}
            ]
        )

        content = response.choices[0].message.content.strip()
        print("🤖 RAW AI:", content)

        match = re.search(r'\{.*\}', content, re.DOTALL)
        if not match:
            print(f"❌ No JSON found for message: {user_message}")
            return {}

        json_text = match.group().strip()
        data = json.loads(json_text)

        if not data.get("task") or not data.get("time"):
            print(f"❌ Incomplete AI output: {data}")
            return {}

        return data

    except Exception as e:
        print(f"❌ Groq error: {e} | message: {user_message}")
        return {}