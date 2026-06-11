# app/agent/loop.py
# Uses manual function-call parsing instead of Groq's tools API,
# which has a known bug with llama-3.3-70b-versatile producing <function=...> format.

import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from groq import Groq
from app.config import GROQ_API_KEY
from app.agent.tools.handlers import dispatch_tool

IST = ZoneInfo("Asia/Kolkata")
client = Groq(api_key=GROQ_API_KEY)
MODEL = "llama-3.3-70b-versatile"
MAX_TURNS = 10

TOOLS_NEEDING_USER_ID = {
    "read_memory", "update_memory", "check_conflicts",
    "save_reminder", "decompose_goal", "send_message",
}

TOOL_DESCRIPTIONS = """You have access to these tools. Call them by outputting JSON in this exact format on its own line:
TOOL_CALL: {"name": "tool_name", "args": {...}}

Available tools:
- read_memory: {"name": "read_memory", "args": {"user_id": "..."}}
- check_conflicts: {"name": "check_conflicts", "args": {"user_id": "...", "proposed_time": "YYYY-MM-DDTHH:MM:00"}}
- fetch_weather: {"name": "fetch_weather", "args": {"latitude": 21.17, "longitude": 72.83, "datetime_str": "YYYY-MM-DDTHH:MM:00"}}
- save_reminder: {"name": "save_reminder", "args": {"user_id": "...", "task": "...", "scheduled_time": "YYYY-MM-DDTHH:MM:00", "recurrence": "none|daily|weekly|hourly"}}
- update_memory: {"name": "update_memory", "args": {"user_id": "...", "updates": {"frequent_tasks": [], "preferred_times": [], "notes": "..."}}}
- decompose_goal: {"name": "decompose_goal", "args": {"user_id": "...", "goal": "...", "context": "..."}}
- send_message: {"name": "send_message", "args": {"user_id": "...", "message": "..."}}

After each TOOL_CALL line, wait for the result before continuing.
When done with all tool calls, write your final reply to the user normally (no TOOL_CALL prefix)."""


def build_system_prompt(memory_profile: str = "") -> str:
    now = datetime.now(IST)
    memory_section = f"User memory:\n{memory_profile}" if memory_profile else "User memory: none yet."
    return f"""You are a smart reminder assistant. Today is {now.strftime('%A, %d %B %Y')}, time is {now.strftime('%I:%M %p')} IST. Year: {now.year}.

{memory_section}

{TOOL_DESCRIPTIONS}

For every reminder request follow this order:
1. TOOL_CALL read_memory
2. TOOL_CALL check_conflicts
3. TOOL_CALL fetch_weather (only if outdoor task: jogging, cycling, walking, picnic, etc.)
4. TOOL_CALL save_reminder
5. TOOL_CALL update_memory
6. Write confirmation to user. Your confirmation MUST include:
   - The task and scheduled time
   - Any conflict warning from check_conflicts if has_conflicts is true
   - Any weather warning from fetch_weather if is_bad is true or rain_chance > 30
   - Recurrence info if not "none"

For goals like "help me build a morning routine", call decompose_goal first, show the plan, then save only after user confirms.

Datetime rules:
- All times IST. Format: YYYY-MM-DDTHH:MM:00
- No date given → use today. Time already passed → use tomorrow."""


def parse_tool_call(line: str):
    """Extract tool name and args from a TOOL_CALL line."""
    line = line.strip()
    if not line.startswith("TOOL_CALL:"):
        return None, None
    json_str = line[len("TOOL_CALL:"):].strip()
    try:
        data = json.loads(json_str)
        return data.get("name"), data.get("args", {})
    except json.JSONDecodeError:
        return None, None


def plan_goal(user_id: str, goal: str, context: str, memory_profile: str) -> str:
    now = datetime.now(IST)
    prompt = f"""Today: {now.strftime('%A, %d %B %Y')}, {now.strftime('%I:%M %p')} IST.
Memory: {memory_profile or 'none'}
Goal: "{goal}" Context: "{context}"
Return ONLY a JSON array, no markdown:
[{{"task":"...","suggested_time":"YYYY-MM-DDTHH:MM:00","recurrence":"daily|weekly|none"}}]"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Return ONLY a valid JSON array. No explanation, no markdown."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
    try:
        plan = json.loads(raw)
        lines = [f"  {i+1}. {r['task']} — {r['suggested_time']} ({r['recurrence']})" for i, r in enumerate(plan)]
        return json.dumps({"plan": plan, "preview": "Proposed plan:\n" + "\n".join(lines)})
    except Exception:
        return json.dumps({"error": "Could not parse goal plan", "raw": raw})


def run_agent(user_message: str, user_id: int) -> str:
    from app.memory import get_memory
    memory_profile = get_memory(user_id) or ""
    memory_profile = memory_profile[:250] if len(memory_profile) > 250 else memory_profile

    messages = [
        {"role": "system", "content": build_system_prompt(memory_profile)},
        {"role": "user", "content": user_message},
    ]

    for turn in range(MAX_TURNS):
        print(f"🔄 Turn {turn + 1}")

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
        )

        reply = response.choices[0].message.content or ""
        print(f"📝 Reply: {reply[:300]}")

        # Check if any line is a tool call
        lines = reply.strip().split("\n")
        tool_results = []
        has_tool_call = False

        for line in lines:
            if line.strip().startswith("TOOL_CALL:"):
                has_tool_call = True
                tool_name, tool_args = parse_tool_call(line)
                if not tool_name:
                    tool_results.append(f"[Error parsing tool call: {line}]")
                    continue

                # Always inject real user_id
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
                tool_results.append(f"TOOL_RESULT ({tool_name}): {result_str}")

        if has_tool_call:
            # Append assistant message and tool results, then loop
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": "\n".join(tool_results) + "\nContinue."})
            continue

        # No tool calls — this is the final reply
        # Strip any leftover TOOL_CALL lines just in case
        final_lines = [l for l in lines if not l.strip().startswith("TOOL_CALL:")]
        return "\n".join(final_lines).strip() or "Done! Your reminder has been set."

    return "Your reminder has been processed. Please check your list."