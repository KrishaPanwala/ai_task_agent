from groq import Groq
from app.config import GROQ_API_KEY
import json

client = Groq(api_key=GROQ_API_KEY)

def extract_task(user_message: str):
    prompt = f"""
    Extract the task and time from the message.

    Message: "{user_message}"

    Return ONLY JSON in this format:
    {{
      "task": "...",
      "time": "..."
    }}
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are an AI that extracts tasks and time from text."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
        timeout=10
    )

    content = response.choices[0].message.content

    try:
        return json.loads(content)
    except:
        return {"error": "Could not parse response", "raw": content}