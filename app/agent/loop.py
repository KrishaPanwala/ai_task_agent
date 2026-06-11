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
MODEL = "llama-3.3-70b-versatile"  # tool-use specific model


# ─── System prompt ────────────────────────────────────────────────────────────

def build_system_prompt(memory_profile: str = "") -> str:
    now = datetime.now(IST)
    today = now.strftime("%A, %d %B %Y")
    time_now = now.strftime("%I:%M %p IST")

    memory_section = (
        f"\n\nUser memory profile:\n{memory_profile}"
        if memory_profile
        else "\n\nUser memory profile: none yet."
    )

    return f"""You are an intelligent reminder agent. Today is {today}, current time is {time_now}.
{memory_section}

Your job is to help users set reminders, plan goals, and stay organised.

When setting a reminder, always:
1. Call read_memory first.
2. Extract task and time. Use memory to fill gaps.
3. Call check_conflicts before saving.
4. If the task is outdoor (jogging, cycling, walking, picnic), call fetch_weather.
5. Call save_reminder only after the above steps.
6. Call update_memory to record new patterns.
7. Reply with a friendly confirmation including any warnings.

For high-level goals like "help me build a morning routine":
- Call decompose_goal first.
- Show the proposed sub-reminders to the user BEFORE saving.
- Only save after the user confirms.

Keep replies friendly and concise. Never show raw JSON to the user.

Datetime rules:
- All times are IST (Asia/Kolkata).
- Output datetimes as ISO 8601: YYYY-MM-DDTHH:MM:00
- If no date mentioned, assume today. If time has passed, use tomorrow.
- Current year is {now.year}."""


# ─── Goal planning pass ───────────────────────────────────────────────────────

def plan_goal(user_id: str, goal: str, context: str, memory_profile: str) -> str:
    now = datetime.now(IST)
    prompt = f"""Today is {now.strftime('%A, %d %B %Y')}, time is {now.strftime('%I:%M %p IST')}.

User memory:
{memory_profile or 'none'}

The user wants to achieve this goal: "{goal}"
Extra context: "{context}"

Break this into 3-6 specific, actionable reminders.
Return ONLY a JSON array, no markdown, no explanation:
[
  {{"task": "...", "suggested_time": "YYYY-MM-DDTHH:MM:00", "recurrence": "daily|weekly|none"}},
  ...
]

Use the user's preferred times from memory when available.
Space reminders sensibly. Use "daily" for habits, "none" for one-off tasks."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Return ONLY a valid JSON array. No explanation, no markdown."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        plan = json.loads(raw)
        lines = [
            f"  {i+1}. {r['task']} - {r['suggested_time']} ({r['recurrence']})"
            for i, r in enumerate(plan)
        ]
        return json.dumps({
            "plan": plan,
            "preview": "Here is the proposed plan:\n" + "\n".join(lines),
        })
    except Exception:
        return json.dumps({"error": "Could not parse goal plan", "raw": raw})


# ─── Tools that require user_id ───────────────────────────────────────────────

TOOLS_NEEDING_USER_ID = {
    "read_memory", "update_memory", "check_conflicts",
    "save_reminder", "decompose_goal", "send_message",
}


# ─── ReAct loop ───────────────────────────────────────────────────────────────

def run_agent(user_message: str, user_id: int) -> str:
    from app.memory import get_memory
    memory_profile = get_memory(user_id) or ""

    messages = [
        {"role": "system", "content": build_system_prompt(memory_profile)},
        {"role": "user", "content": user_message},
    ]

    for turn in range(MAX_TURNS):
        response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=0.2,
        parallel_tool_calls=False,
    )

        choice = response.choices[0]
        msg = choice.message

        # ── Final text response ────────────────────────────────────────────
        if choice.finish_reason == "stop":
            return msg.content or "Done! Your reminder has been set."

        # ── Tool calls ─────────────────────────────────────────────────────
        if choice.finish_reason == "tool_calls" and msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
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

                print(f"🔧 Tool: {tool_name}({tool_args})")

                # Inject user_id if missing
                if tool_name in TOOLS_NEEDING_USER_ID:
                    tool_args["user_id"] = str(user_id)

                # Goal decomposition gets its own LLM pass
                if tool_name == "decompose_goal":
                    result_str = plan_goal(
                        user_id=str(user_id),
                        goal=tool_args.get("goal", ""),
                        context=tool_args.get("context", ""),
                        memory_profile=memory_profile,
                    )
                else:
                    result_str = dispatch_tool(tool_name, tool_args)

                print(f"✅ Result: {result_str[:120]}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

            continue

        # Unexpected finish reason
        return msg.content or "I have processed your request."

    return "I processed your request but hit a complexity limit. Please try rephrasing."