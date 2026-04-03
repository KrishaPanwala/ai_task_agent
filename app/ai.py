from groq import Groq
from app.config import GROQ_API_KEY
import json
import re

client = Groq(api_key=GROQ_API_KEY)


def extract_task(user_message: str):

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

        content = response.choices[0].message.content

        json_text = re.search(r'\{.*\}', content, re.DOTALL).group()

        return json.loads(json_text)

    except Exception as e:
        print("Groq error:", e)
        return {"error": str(e)}