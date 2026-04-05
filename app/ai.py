from groq import Groq
from app.config import GROQ_API_KEY
import json
import re

client = Groq(api_key=GROQ_API_KEY)


def extract_task(user_message: str) -> dict:

    prompt = f"""
    Extract task and time from this message.

    Message: {user_message}

    Return only JSON:

    {{
        "task": "",
        "time": ""
    }}
    """

    try:

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Extract task and time"},
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

        # validate fields
        if not data.get("task") or not data.get("time"):
            print(f"❌ Incomplete AI output: {data}")
            return {}

        return data

    except Exception as e:
        print(f"❌ Groq error: {e} | message: {user_message}")
        return {}