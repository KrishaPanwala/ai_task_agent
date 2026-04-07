# app/ai.py
from groq import Groq
from app.config import GROQ_API_KEY
import json
import re

client = Groq(api_key=GROQ_API_KEY)

def extract_task(user_message: str) -> dict:
    prompt = f"""Extract task, time, and recurrence from this message: "{user_message}"

Return ONLY this JSON, nothing else, no explanation, no markdown:
{{"task": "", "time": "", "is_recurring": false, "recur_type": null, "recur_value": null}}

Rules:
- "every day" or "daily" or "everyday" → is_recurring=true, recur_type="daily"
- "every hour" → is_recurring=true, recur_type="hourly"
- "every X minutes" → is_recurring=true, recur_type="interval", recur_value="X"
- "every monday/tuesday/etc" → is_recurring=true, recur_type="weekly", recur_value="monday"
- No recurrence → is_recurring=false, recur_type=null, recur_value=null"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a JSON extractor. Return ONLY valid JSON. No explanation, no markdown, no extra text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0  # ✅ makes output more deterministic
        )

        content = response.choices[0].message.content.strip()
        print("🤖 RAW AI:", content)

        # ✅ Strip markdown code blocks if present
        content = re.sub(r'```json|```', '', content).strip()

        # ✅ Extract first JSON object
        match = re.search(r'\{.*?\}', content, re.DOTALL)
        if not match:
            print(f"❌ No JSON found for message: {user_message}")
            return {}

        data = json.loads(match.group().strip())

        if not data.get("task") or not data.get("time"):
            print(f"❌ Incomplete AI output: {data}")
            return {}

        return data

    except Exception as e:
        print(f"❌ Groq error: {e} | message: {user_message}")
        return {}