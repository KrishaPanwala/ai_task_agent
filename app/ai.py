from groq import Groq
from app.config import GROQ_API_KEY
import json

client = Groq(api_key=GROQ_API_KEY)


def extract_task(user_message: str):

    prompt = f"""
    Extract task and time.

    Message: {user_message}

    Return JSON:
    {{
        "task": "",
        "time": ""
    }}
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Extract task and time"},
            {"role": "user", "content": prompt}
        ]
    )

    content = response.choices[0].message.content

    try:
        return json.loads(content)
    except:
        return {"error": content}