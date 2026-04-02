from groq import Groq
from app.config import GROQ_API_KEY
import json
import re

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
            {
                "role": "system",
                "content": "You extract task and time and return only JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=100
    )

    content = response.choices[0].message.content

    try:
        # extract JSON from response safely
        json_match = re.search(r"\{.*\}", content, re.DOTALL)

        if json_match:
            clean_json = json_match.group()
            return json.loads(clean_json)

        return {"error": "Could not parse response", "raw": content}

    except Exception as e:
        return {"error": "Could not parse response", "raw": content}