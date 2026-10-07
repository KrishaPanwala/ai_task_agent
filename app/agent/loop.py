# app/agent/loop.py

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from groq import Groq

from app.config import GROQ_API_KEY
from app.agent.tools.handlers import dispatch_tool
from app.agent.tools.schemas import TOOLS

IST = ZoneInfo("Asia/Kolkata")

client = Groq(api_key=GROQ_API_KEY)

MODEL = "openai/gpt-oss-20b"
MAX_TURNS = 10


def build_system_prompt(memory_profile: str = "") -> str:
    now = datetime.now(IST)

    memory_section = (
        f"User memory:\n{memory_profile}"
        if memory_profile
        else "User memory: none yet."
    )

    return f"""
You are a smart reminder assistant.

Current date:
{now.strftime('%A, %d %B %Y')}

Current time:
{now.strftime('%I:%M %p')} IST

Year:
{now.year}

All reminder times are in Asia/Kolkata (IST).

{memory_section}

IMPORTANT TOOL RULES:

1. For a normal reminder request, follow this order:
   - read_memory
   - check_conflicts
   - fetch_weather only if the task is outdoor/weather-sensitive
   - save_reminder
   - update_memory

2. Always call read_memory before scheduling a reminder.

3. Always call check_conflicts before save_reminder.

4. Only call fetch_weather for outdoor/weather-sensitive tasks such as:
   - jogging
   - running
   - cycling
   - walking
   - picnic
   - outdoor exercise
   - outdoor events

5. Do NOT call fetch_weather for indoor tasks.

6. Do not save a reminder until its date and time are determined.

7. If the user gives only a time, use today's date.

8. If the requested time has already passed today, use tomorrow.

9. Tool datetime values must use:
   YYYY-MM-DDTHH:MM:SS

10. Interpret reminder times as IST.

11. When calling tools, always use the actual user ID supplied by the application.
    Never invent or change the user ID.

12. For a goal such as:
    "help me build a morning routine"
    use decompose_goal first.
    Do not automatically save the proposed reminders unless the user confirms.

13. After tools finish, give a short confirmation.

The final confirmation should include:
- task
- scheduled time
- recurrence if applicable
- conflict warning if there is a conflict
- weather warning if weather is bad or rain chance is above 30%

Format the final answer like:

✅ [task] set for [DD Mon YYYY at HH:MM AM/PM]
⚠️ [conflict warning if needed]
🌤️ [weather warning if needed]

Keep the final response under 3 lines.
"""


def _normalize_tool_args(tool_name: str, args: dict, user_id: int) -> dict:
    """
    Make tool arguments safe before passing them to handlers.
    The authenticated user_id always wins over whatever the model provides.
    """

    args = dict(args or {})

    # Never trust the model for user identity.
    if tool_name in {
        "read_memory",
        "update_memory",
        "check_conflicts",
        "save_reminder",
        "decompose_goal",
        "send_message",
    }:
        args["user_id"] = str(user_id)

    # schemas.py calls this field "datetime",
    # but handlers.py expects "datetime_str".
    if tool_name == "fetch_weather":
        if "datetime" in args and "datetime_str" not in args:
            args["datetime_str"] = args.pop("datetime")

    return args


def _execute_tool(tool_name: str, args: dict, user_id: int) -> str:
    """
    Execute one native Groq tool call through the existing dispatcher.
    """

    args = _normalize_tool_args(tool_name, args, user_id)

    print(f"🔧 {tool_name}({args})")

    result = dispatch_tool(tool_name, args)

    print(f"✅ {result[:500]}")

    return result


def plan_goal(
    user_id: str,
    goal: str,
    context: str,
    memory_profile: str,
) -> str:
    """
    Generate a proposed goal plan.
    This is deliberately a separate LLM call with no tools.
    """

    now = datetime.now(IST)

    prompt = f"""
Today: {now.strftime('%A, %d %B %Y')}
Current time: {now.strftime('%I:%M %p')} IST

User memory:
{memory_profile or 'none'}

Goal:
{goal}

Context:
{context}

Return ONLY a valid JSON array.

Each item must have exactly:
- task
- suggested_time
- recurrence

Example:

[
  {{
    "task": "Morning exercise",
    "suggested_time": "2026-10-09T07:00:00",
    "recurrence": "daily"
  }}
]

Do not include markdown.
Do not include explanations.
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a planning assistant. "
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.2,
        max_tokens=800,
    )

    raw = (response.choices[0].message.content or "").strip()

    # Remove accidental markdown fences.
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        plan = json.loads(raw)

        if not isinstance(plan, list):
            raise ValueError("Plan is not a JSON array")

        lines = []

        for i, item in enumerate(plan, 1):
            lines.append(
                f"{i}. {item['task']} — "
                f"{item['suggested_time']} "
                f"({item['recurrence']})"
            )

        return json.dumps(
            {
                "plan": plan,
                "preview": "Proposed plan:\n" + "\n".join(lines),
            },
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps(
            {
                "error": "Could not parse goal plan",
                "details": str(e),
                "raw": raw,
            },
            ensure_ascii=False,
        )


def run_agent(user_message: str, user_id: int) -> str:
    """
    Main AI agent.

    Uses Groq's native function calling rather than manually asking
    the model to output TOOL_CALL text.
    """

    from app.memory import get_memory

    # Keep the existing memory context in the system prompt.
    memory_profile = get_memory(user_id) or ""

    # Avoid putting a huge memory profile into every request.
    memory_profile = memory_profile[:250]

    messages = [
        {
            "role": "system",
            "content": build_system_prompt(memory_profile),
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    for turn in range(MAX_TURNS):
        print(f"🔄 Agent turn {turn + 1}")

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=1024,
        )

        message = response.choices[0].message

        # ---------------------------------------------------------
        # Native tool calls
        # ---------------------------------------------------------

        tool_calls = getattr(message, "tool_calls", None)

        if tool_calls:
            print(f"🛠️ Model requested {len(tool_calls)} tool call(s)")

            # Add the assistant's tool-call message to conversation.
            messages.append(message)

            for tool_call in tool_calls:
                tool_name = tool_call.function.name

                try:
                    tool_args = json.loads(
                        tool_call.function.arguments or "{}"
                    )
                except json.JSONDecodeError as e:
                    result = json.dumps(
                        {
                            "error": "Invalid tool arguments",
                            "details": str(e),
                        }
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        }
                    )

                    continue

                # -------------------------------------------------
                # Special handling for goal decomposition
                # -------------------------------------------------

                if tool_name == "decompose_goal":
                    tool_args = _normalize_tool_args(
                        tool_name,
                        tool_args,
                        user_id,
                    )

                    result = plan_goal(
                        user_id=str(user_id),
                        goal=tool_args.get("goal", ""),
                        context=tool_args.get("context", ""),
                        memory_profile=memory_profile,
                    )

                else:
                    result = _execute_tool(
                        tool_name,
                        tool_args,
                        user_id,
                    )

                # IMPORTANT:
                # Native Groq tool results must be sent as role="tool"
                # with the matching tool_call_id.
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

            # Ask the model what to do next after receiving tool results.
            continue

        # ---------------------------------------------------------
        # No tool call = final answer
        # ---------------------------------------------------------

        reply = message.content or ""

        print(f"📝 Final reply: {reply[:500]}")

        return reply.strip() or "Done! Your reminder has been set."

    return "Your reminder has been processed. Please check your reminder list."
