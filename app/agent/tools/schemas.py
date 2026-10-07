"""
Tool schemas passed to Groq for native function calling.

The model does NOT receive user_id as a parameter.
The application injects the actual user_id automatically.
"""

TOOLS = [

    # ------------------------------------------------------------------
    # MEMORY
    # ------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "read_memory",
            "description": (
                "Read the user's memory profile including preferred "
                "reminder times, frequent tasks, habits, and past behaviour. "
                "Always call this FIRST before scheduling a reminder."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "update_memory",
            "description": (
                "Update the user's memory profile after an interaction. "
                "Store new habits, preferred times, or task patterns."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "object",
                        "description": "Information to add to user memory.",
                        "properties": {
                            "preferred_times": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Examples: morning, 7am, after lunch"
                                ),
                            },
                            "frequent_tasks": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Examples: exercise, drink water, meditate"
                                ),
                            },
                            "habits": {
                                "type": "object",
                                "description": "Free-form habit information.",
                            },
                            "notes": {
                                "type": "string",
                                "description": "Additional memory notes.",
                            },
                        },
                    }
                },
                "required": ["updates"],
            },
        },
    },

    # ------------------------------------------------------------------
    # CONFLICTS
    # ------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "check_conflicts",
            "description": (
                "Check whether existing reminders overlap with a proposed "
                "time. Always call this before saving a reminder."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "proposed_time": {
                        "type": "string",
                        "description": (
                            "Reminder time in IST using "
                            "YYYY-MM-DDTHH:MM:SS format."
                        ),
                    },
                    "window_minutes": {
                        "type": "integer",
                        "description": (
                            "Minutes before and after the proposed time "
                            "to check. Default is 15."
                        ),
                        "default": 15,
                    },
                },
                "required": ["proposed_time"],
            },
        },
    },

    # ------------------------------------------------------------------
    # WEATHER
    # ------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "fetch_weather",
            "description": (
                "Fetch weather forecast for a given location and time. "
                "Use only for outdoor or weather-sensitive tasks such as "
                "jogging, cycling, walking, picnic, or outdoor exercise."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude of the location.",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude of the location.",
                    },
                    "datetime_str": {
                        "type": "string",
                        "description": (
                            "IST datetime using "
                            "YYYY-MM-DDTHH:MM:SS format."
                        ),
                    },
                },
                "required": [
                    "latitude",
                    "longitude",
                    "datetime_str",
                ],
            },
        },
    },

    # ------------------------------------------------------------------
    # SAVE REMINDER
    # ------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "save_reminder",
            "description": (
                "Save a validated reminder for the current user. "
                "The application automatically supplies the user's identity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "What to remind the user about.",
                    },
                    "scheduled_time": {
                        "type": "string",
                        "description": (
                            "Reminder time in IST using "
                            "YYYY-MM-DDTHH:MM:SS format."
                        ),
                    },
                    "recurrence": {
                        "type": "string",
                        "enum": [
                            "none",
                            "daily",
                            "weekly",
                            "hourly",
                        ],
                        "default": "none",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional tags such as outdoor, health, or work."
                        ),
                    },
                },
                "required": [
                    "task",
                    "scheduled_time",
                ],
            },
        },
    },

    # ------------------------------------------------------------------
    # GOAL DECOMPOSITION
    # ------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "decompose_goal",
            "description": (
                "Break a high-level goal into a structured list of "
                "sub-reminders with suggested times. Use for requests such "
                "as 'help me build a morning routine' or "
                "'I want to study for exams'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "The user's high-level goal.",
                    },
                    "context": {
                        "type": "string",
                        "description": (
                            "Extra context such as duration, deadline, "
                            "or constraints."
                        ),
                    },
                },
                "required": ["goal"],
            },
        },
    },

    # ------------------------------------------------------------------
    # SEND TELEGRAM MESSAGE
    # ------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": (
                "Send a Telegram message to the current user. "
                "Use for proactive outreach, warnings, or confirmations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to send to the user.",
                    },
                    "reply_markup": {
                        "type": "object",
                        "description": (
                            "Optional Telegram inline keyboard JSON."
                        ),
                    },
                },
                "required": ["message"],
            },
        },
    },
]
