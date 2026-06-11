# app/agent/loop.py
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from groq import Groq
from app.config import GROQ_API_KEY
from app.agent.tools.schemas import TOOLS
from app.agent.tools.handlers import dispatch_tool

IST = ZoneInfo("Asia/Kolkata")
client = Groq(api_key=GROQ_API_KEY)

MAX_TURNS = 8
MODEL = "llama-3.3-70b-versatile"

TOOLS_NEEDING_USER_ID = {
    "read_memory", "update_memory", "check_conflicts",
    "save_reminder", "decompose_goal", "send_message",
}


def build_system_prompt(memory_profile: str = "") -> str:
    now = datetime.now(IST)
    memory_section = f"User memory:\n{memory_profile}" if memory_profile else "User memory: none yet."
    return f"""You are a reminder assistant. Today is {now.strftime('%A, %d %B %Y')}, time is {now.strftime('%I:%M %p')} IST. Year: {now.year}.

{memory_section}

For every reminder request, call tools in this exact order:
1. read_memory
2. check_conflicts
3. fetch_weather (outdoor tasks only: jogging, cycling, walking, etc.)
4. save_reminder
5. update_memory
Then reply with a short confirmation.

For goals ("build a routine", "study plan"), call decompose_goal first and show the plan before saving.

Always output datetimes as YYYY-MM-DDTHH:MM:00 in IST. If no date given, use today; if time passed, use tomorrow."""


def plan_goal(user_id: str, goal: str, context: str, memory_profile: str) -> str:
    now = datetime.now(IST)
    prompt = f"""Today: {now.strftime('%A, %d %B %Y')}, {now.strftime('%I:%M %p')} IST.
Memory: {memory_profile or 'none'}
Goal: "{goal}" Context: "{context}"
Return ONLY a JSON array:
[{{"task":"...","suggested_time":"YYYY-MM-DDTHH:MM:00","recurrence":"daily|weekly|none"}}]"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Return ONLY a valid JSON array. No markdown."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
    try:
        plan = json.loads(raw)
        lines = [f"  {i+1}. {r['task']} - {r['suggested_time']} ({r['recurrence']})" for i, r in enumerate(plan)]
        return json.dumps({"plan": plan, "preview": "Proposed plan:\n" + "\n".join(lines)})
    except Exception:
        return json.dumps({"error": "Could not parse goal plan", "raw": raw})


def run_agent(user_message: str, user_id: int) -> str:
    from app.memory import get_memory
    memory_profile = get_memory(user_id) or ""

    messages = [
        {"role": "system", "content": build_system_prompt(memory_profile)},
        {"role": "user", "content": user_message},
    ]

    for turn in range(MAX_TURNS):
        print(f"🔄 Turn {turn + 1}")

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0,
                parallel_tool_calls=False,
            )
        except Exception as e:
            print(f"❌ Groq error: {e}")
            raise

        choice = response.choices[0]
        msg = choice.message
        print(f"finish_reason={choice.finish_reason} | tool_calls={bool(msg.tool_calls)}")

        if choice.finish_reason == "stop":
            return msg.content or "Done! Your reminder has been set."

        if choice.finish_reason == "tool_calls" and msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                # Always inject real user_id — never trust what model provides
                if tool_name in TOOLS_NEEDING_USER_ID:
                    tool_args["user_id"] = str(user_id)

                print(f"🔧 {tool_name}({tool_args})")

                if tool_name == "decompose_goal":
                    result_str = plan_goal(
                        user_id=str(user_id),
                        goal=tool_args.get("goal", ""),
                        context=tool_args.get("context", ""),
                        memory_profile=memory_profile,
                    )
                else:
                    result_str = dispatch_tool(tool_name, tool_args)

                print(f"✅ {result_str[:200]}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

            continue

        print(f"⚠️ Unexpected finish_reason: {choice.finish_reason}")
        return msg.content or "Request processed."

    return "Request processed. Please check your reminders."