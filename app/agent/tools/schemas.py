"""
Tool schemas passed to Groq for function calling.
Each tool maps to a handler in tools/handlers.py
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_memory",
            "description": (
                "Read the user's memory profile: preferred reminder times, "
                "frequent tasks, habits, and past behaviour. "
                "Always call this FIRST before scheduling anything."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The user's ID"}
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_memory",
            "description": (
                "Update the user's memory profile after an interaction. "
                "Store new habits, preferred times, or task patterns observed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "updates": {
                        "type": "object",
                        "description": "Key-value pairs to merge into the memory profile",
                        "properties": {
                            "preferred_times": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "e.g. ['morning', '7am', 'after lunch']",
                            },
                            "frequent_tasks": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "e.g. ['exercise', 'drink water', 'meditate']",
                            },
                            "habits": {
                                "type": "object",
                                "description": "Free-form habit notes, e.g. {skips_early_alarms: true}",
                            },
                            "notes": {"type": "string"},
                        },
                    },
                },
                "required": ["user_id", "updates"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_conflicts",
            "description": (
                "Check if any existing reminders overlap with a proposed time. "
                "Call this before saving any reminder."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "proposed_time": {
                        "type": "string",
                        "description": "ISO 8601 datetime string, e.g. 2025-06-01T17:00:00",
                    },
                    "window_minutes": {
                        "type": "integer",
                        "description": "How many minutes either side to check. Default 15.",
                        "default": 15,
                    },
                },
                "required": ["user_id", "proposed_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_weather",
            "description": (
                "Fetch weather forecast for a given location and time. "
                "Call this when the task sounds outdoor or weather-sensitive "
                "(jogging, cycling, walking, picnic, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "datetime": {
                        "type": "string",
                        "description": "ISO 8601 datetime to check forecast for",
                    },
                },
                "required": ["latitude", "longitude", "datetime"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_reminder",
            "description": "Save a fully validated reminder to Supabase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "task": {"type": "string", "description": "What to remind the user about"},
                    "scheduled_time": {
                        "type": "string",
                        "description": "ISO 8601 datetime string in UTC",
                    },
                    "recurrence": {
                        "type": "string",
                        "enum": ["none", "daily", "weekly", "hourly"],
                        "default": "none",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "e.g. ['outdoor', 'health', 'work']",
                    },
                },
                "required": ["user_id", "task", "scheduled_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decompose_goal",
            "description": (
                "Break a high-level goal into a structured list of sub-reminders "
                "with suggested times. Use when the user says something like "
                "'help me build a morning routine' or 'I want to study for exams'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "goal": {"type": "string", "description": "The user's high-level goal"},
                    "context": {
                        "type": "string",
                        "description": "Any extra context: duration, deadline, constraints",
                    },
                },
                "required": ["user_id", "goal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": (
                "Send a Telegram message to the user. Use for proactive outreach, "
                "warnings (weather, conflicts), or goal plan confirmations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "message": {"type": "string"},
                    "reply_markup": {
                        "type": "object",
                        "description": "Optional Telegram inline keyboard JSON",
                    },
                },
                "required": ["user_id", "message"],
            },
        },
    },
]
