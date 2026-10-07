# app/agent/loop.py

import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from groq import Groq

from app.config import GROQ_API_KEY
from app.agent.tools.handlers import dispatch_tool
from app.agent.tools.schemas import TOOLS

IST = ZoneInfo("Asia/Kolkata")

client = Groq(api_key=GROQ_API_KEY)

MODEL = "openai/gpt-oss-20b"
MAX_TURNS = 10


# Tools where the real user_id is supplied by Python.
# The LLM never needs to provide it.
USER_TOOLS = {
    "read_memory",
    "update_memory",
    "check_conflicts",
    "save_reminder",
    "decompose_goal",
    "send_message",
}


# ----------------------------------------------------------------------
# SYSTEM PROMPT
# ----------------------------------------------------------------------

def build_system_prompt(memory_profile: str = "") -> str:
    now = datetime.now(IST)

    if memory_profile:
        memory_section = f"User memory:\n{memory_profile}"
    else:
        memory_section = "User memory: none yet."

    return f"""
You are a smart reminder assistant.

Current date:
{now.strftime('%A, %d %B %Y')}

Current time:
{now.strftime('%I:%M %p')} IST

Timezone:
Asia/Kolkata (IST)

{memory_section}

IMPORTANT RULES:

1. All reminder times are in IST.

2. For a normal reminder request, use this order:
   read_memory
   -> check_conflicts
   -> fetch_weather if needed
   -> save_reminder
   -> update_memory

3. Always call read_memory before scheduling.

4. Always call check_conflicts before save_reminder.

5. Only use fetch_weather for outdoor/weather-sensitive tasks.

6. Outdoor examples:
   jogging, running, cycling, walking, picnic,
   outdoor exercise, outdoor events.

7. Do not use weather for normal indoor reminders.

8. Relative time expressions such as:
   "in 2 minutes"
   "in 10 minutes"
   "in 1 hour"
   "after 30 minutes"
   are relative to the current IST time.

9. The application supplies the user's identity automatically.
   NEVER ask the user for a user ID.

10. NEVER mention or request an internal user ID.

11. If only a clock time is given, use today's date.

12. If a requested clock time has already passed today,
    use tomorrow.

13. Tool datetime format:
    YYYY-MM-DDTHH:MM:SS

14. For goal requests such as:
    "help me build a morning routine"
    use decompose_goal first.
    Do not automatically save the proposed reminders unless
    the user confirms.

15. After all required tools finish, give a short confirmation.

Final format:

✅ [task] set for [DD Mon YYYY at HH:MM AM/PM]
⚠️ [conflict warning if needed]
🌤️ [weather warning if needed]

Keep the final response under 3 lines.
"""


# ----------------------------------------------------------------------
# RELATIVE TIME
# ----------------------------------------------------------------------

def resolve_relative_time(user_message: str):
    """
    Detect relative expressions such as:

        in 2 minutes
        in 10 mins
        in 1 hour
        after 30 minutes
        in 2 hours

    The calculation is performed by Python, not the LLM.
    """

    text = user_message.lower().strip()

    match = re.search(
        r"\b(?:in|after)\s+"
        r"(\d+(?:\.\d+)?)\s*"
        r"(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b",
        text,
    )

    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2)

    now = datetime.now(IST)

    if unit.startswith(("second", "sec")):
        target = now + timedelta(seconds=amount)

    elif unit.startswith(("minute", "min")):
        target = now + timedelta(minutes=amount)

    elif unit.startswith(("hour", "hr")):
        target = now + timedelta(hours=amount)

    elif unit.startswith("day"):
        target = now + timedelta(days=amount)

    else:
        return None

    # Keep seconds because the scheduler checks every 10 seconds.
    return target.replace(microsecond=0)


# ----------------------------------------------------------------------
# DATETIME
# ----------------------------------------------------------------------

def datetime_to_iso(dt: datetime) -> str:
    """
    Convert datetime to the format expected by handlers.py.

    The project stores reminder times as naive IST datetimes.
    """

    if dt.tzinfo is not None:
        dt = dt.astimezone(IST)

    return dt.replace(
        tzinfo=None,
        microsecond=0,
    ).isoformat()


# ----------------------------------------------------------------------
# TOOL ARGUMENT NORMALIZATION
# ----------------------------------------------------------------------

def normalize_tool_args(
    tool_name: str,
    args: dict,
    user_id: int,
    relative_time=None,
) -> dict:
    """
    Prepare model-generated arguments before dispatching.

    The important part is that Python supplies the actual user_id.
    """

    args = dict(args or {})

    # --------------------------------------------------------------
    # Inject real application user ID.
    # --------------------------------------------------------------

    if tool_name in USER_TOOLS:
        args["user_id"] = str(user_id)

    # --------------------------------------------------------------
    # Force relative time calculated by Python.
    # --------------------------------------------------------------

    if relative_time is not None:

        if tool_name == "check_conflicts":
            args["proposed_time"] = datetime_to_iso(
                relative_time
            )

        elif tool_name == "save_reminder":
            args["scheduled_time"] = datetime_to_iso(
                relative_time
            )

    return args


# ----------------------------------------------------------------------
# TOOL EXECUTION
# ----------------------------------------------------------------------

def execute_tool(
    tool_name: str,
    args: dict,
    user_id: int,
    relative_time=None,
) -> str:

    args = normalize_tool_args(
        tool_name=tool_name,
        args=args,
        user_id=user_id,
        relative_time=relative_time,
    )

    print(f"🔧 {tool_name}({args})")

    result = dispatch_tool(
        tool_name,
        args,
    )

    print(f"✅ {result[:500]}")

    return result


# ----------------------------------------------------------------------
# GOAL PLANNING
# ----------------------------------------------------------------------

def plan_goal(
    user_id: str,
    goal: str,
    context: str,
    memory_profile: str,
) -> str:

    now = datetime.now(IST)

    prompt = f"""
Today:
{now.strftime('%A, %d %B %Y')}

Current time:
{now.strftime('%I:%M %p')} IST

User memory:
{memory_profile or 'none'}

Goal:
{goal}

Context:
{context}

Create a useful reminder plan.

Return ONLY a valid JSON array.

Each item must contain:

task
suggested_time
recurrence

Example:

[
  {{
    "task": "Morning exercise",
    "suggested_time": "2026-10-09T07:00:00",
    "recurrence": "daily"
  }}
]

Do not use markdown.
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

    raw = (
        response.choices[0].message.content or ""
    ).strip()

    raw = (
        raw
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

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
                "preview": (
                    "Proposed plan:\n"
                    + "\n".join(lines)
                ),
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


# ----------------------------------------------------------------------
# MAIN AGENT
# ----------------------------------------------------------------------

def run_agent(
    user_message: str,
    user_id: int,
) -> str:

    from app.memory import get_memory

    # --------------------------------------------------------------
    # Existing memory is used as context.
    # --------------------------------------------------------------

    memory_profile = get_memory(user_id) or ""
    memory_profile = memory_profile[:250]

    # --------------------------------------------------------------
    # Detect relative time BEFORE asking the LLM.
    # --------------------------------------------------------------

    relative_time = resolve_relative_time(
        user_message
    )

    if relative_time:
        print(
            "⏱️ Relative time detected: "
            f"{relative_time.strftime('%d %b %Y %I:%M:%S %p IST')}"
        )

    # --------------------------------------------------------------
    # Conversation
    # --------------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": build_system_prompt(
                memory_profile
            ),
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    # --------------------------------------------------------------
    # Agent loop
    # --------------------------------------------------------------

    for turn in range(MAX_TURNS):

        print(f"🔄 Agent turn {turn + 1}")

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            parallel_tool_calls=False,
            temperature=0.2,
            max_tokens=1024,
        )

        message = response.choices[0].message

        tool_calls = getattr(
            message,
            "tool_calls",
            None,
        )

        # ==========================================================
        # TOOL CALL
        # ==========================================================

        if tool_calls:

            print(
                f"🛠️ Model requested "
                f"{len(tool_calls)} tool call(s)"
            )

            # Convert SDK message into a dictionary.
            messages.append(
                message.model_dump(
                    exclude_none=True
                )
            )

            for tool_call in tool_calls:

                tool_name = (
                    tool_call.function.name
                )

                raw_arguments = (
                    tool_call.function.arguments
                    or "{}"
                )

                # --------------------------------------------------
                # Parse arguments
                # --------------------------------------------------

                try:

                    tool_args = json.loads(
                        raw_arguments
                    )

                except json.JSONDecodeError as e:

                    result = json.dumps(
                        {
                            "error": (
                                "Invalid tool arguments"
                            ),
                            "details": str(e),
                        }
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": (
                                tool_call.id
                            ),
                            "content": result,
                        }
                    )

                    continue

                # --------------------------------------------------
                # Goal decomposition
                # --------------------------------------------------

                if tool_name == "decompose_goal":

                    tool_args = normalize_tool_args(
                        tool_name,
                        tool_args,
                        user_id,
                        relative_time,
                    )

                    result = plan_goal(
                        user_id=str(user_id),
                        goal=tool_args.get(
                            "goal",
                            "",
                        ),
                        context=tool_args.get(
                            "context",
                            "",
                        ),
                        memory_profile=memory_profile,
                    )

                # --------------------------------------------------
                # Normal tools
                # --------------------------------------------------

                else:

                    result = execute_tool(
                        tool_name=tool_name,
                        args=tool_args,
                        user_id=user_id,
                        relative_time=relative_time,
                    )

                # --------------------------------------------------
                # Send native tool result back to Groq.
                # --------------------------------------------------

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": (
                            tool_call.id
                        ),
                        "content": result,
                    }
                )

            continue

        # ==========================================================
        # FINAL ANSWER
        # ==========================================================

        reply = (
            message.content or ""
        ).strip()

        print(
            f"📝 Final reply: {reply[:500]}"
        )

        if reply:
            return reply

        return (
            "✅ Done! Your reminder has been set."
        )

    return (
        "Your reminder has been processed. "
        "Please check your reminder list."
    )
