# 🤖 AI Reminder Bot

A full-stack intelligent reminder system where users set reminders using natural language — through a web dashboard or Telegram bot. Powered by a ReAct agent that reasons, uses tools, remembers habits, and acts proactively.

> Just type *"remind me to drink water at 5pm"* — the AI handles everything else.

---

## ✨ Features

- 🧠 **Natural language parsing** — no forms, no dropdowns, just type
- 🔁 **Recurring reminders** — daily, weekly, hourly, or custom intervals
- ⚔️ **Conflict detection** — warns if a new reminder overlaps an existing one
- 🌤️ **Weather awareness** — checks forecast for outdoor tasks and warns if bad weather expected
- 🧬 **Persistent memory** — learns your habits and preferred times over time
- 🎯 **Goal planning** — breaks high-level goals into sub-reminders ("help me build a morning routine")
- 📣 **Proactive outreach** — agent reaches out daily if it notices clusters or issues with your schedule
- 📊 **Web dashboard** — countdown timers, day planner, weekly grid view
- 🔔 **Telegram notifications** — reminders with Done / Snooze 10min / Snooze 1hr buttons
- 👥 **Multi-user** — full JWT auth with hashed passwords

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| AI | Groq — LLaMA 3.3 70b |
| Database | Supabase (PostgreSQL) |
| Notifications | Telegram Bot API |
| Hosting | Render |
| Auth | JWT + bcrypt |
| Weather | Open-Meteo (free, no API key) |

---

## 🏗 Architecture

```
User (Web Dashboard or Telegram)
        ↓
   FastAPI Backend
        ↓
   ReAct Agent Loop (app/agent/loop.py)
        ↓
   ┌────────────────────────────────────┐
   │  Tools                             │
   │  ├── read_memory                   │
   │  ├── check_conflicts               │
   │  ├── fetch_weather                 │
   │  ├── save_reminder                 │
   │  ├── update_memory                 │
   │  ├── decompose_goal                │
   │  └── send_message                  │
   └────────────────────────────────────┘
        ↓
   Supabase PostgreSQL
        ↓
   Scheduler (every 10s) → Telegram Notification
```

---

## 🤖 How the Agent Works

This project uses a **ReAct (Reason + Act) loop** — the AI reasons about what to do, calls tools, observes results, and repeats until it has a final answer.

For every reminder request the agent follows this pipeline:

```
1. read_memory      → load user habits and preferences
2. check_conflicts  → check for overlapping reminders
3. fetch_weather    → check forecast
4. save_reminder    → write to database
5. update_memory    → record new patterns
6. Reply to user    → friendly confirmation with warnings
```

Instead of Groq's native tools API (which has a bug with llama-3.3-70b producing `<function=...>` XML format), the agent uses **plain text tool calling**:

```
LLM outputs:
TOOL_CALL: {"name": "read_memory", "args": {"user_id": "1"}}

App executes the tool and feeds back:
TOOL_RESULT (read_memory): {"found": true, "profile": "prefers 7am..."}

LLM continues to next tool or writes final reply.
```

---

## 📁 Project Structure

```
app/
├── main.py                  # FastAPI app, all HTTP endpoints
├── telegram_bot.py          # Telegram handlers
├── telegram_bot_runner.py   # Starts bot in background
├── scheduler.py             # Background thread, fires reminders every 10s
├── ai.py                    # Original Groq parser (kept as reference)
├── auth.py                  # JWT login, password hashing
├── config.py                # Environment variables
├── db.py                    # SQLAlchemy connection
├── models.py                # Task, User, UserMemory models
├── memory.py                # Read/write user memory profiles
├── weather.py               # Open-Meteo weather fetching
├── conflict.py              # Overlap detection
├── telegram.py              # send_telegram_message helper
│
└── agent/
    ├── loop.py              # ReAct agent brain
    ├── proactive.py         # Daily proactive outreach
    └── tools/
        ├── schemas.py       # Tool definitions
        └── handlers.py      # Tool implementations
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Supabase account (free tier)
- Groq API key (free tier)
- Telegram bot token (from @BotFather)

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/ai-reminder-bot.git
cd ai-reminder-bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set environment variables

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=your_supabase_postgresql_url
SECRET_KEY=your_jwt_secret_key
```

### 4. Run locally

```bash
uvicorn app.main:app --reload
```

### 5. Set Telegram webhook

```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-domain.com/webhook/<TOKEN>
```

---

## 💬 Usage

### Web Dashboard
1. Register at `/register`
2. Get your Telegram Chat ID by messaging your bot `/start`
3. Paste the Chat ID in your profile
4. Type naturally in the input box: *"remind me to exercise at 6am daily"*

### Telegram Bot
Just message the bot directly:
```
remind me to drink water every hour
help me build a morning routine
remind me to call mom on sunday at 5pm
remind me to go jogging at 7am tomorrow
```

### Commands
```
/start  — get your Chat ID
/list   — view all pending reminders
/delete <id> — delete a reminder
/clear  — delete all reminders
```

---

## 🧠 Memory System

After every reminder the agent updates a memory profile for the user:

```
User sets "remind me to jog at 6am"
    ↓
Memory updated: "user prefers 6am for exercise"
    ↓
Next time user says "remind me to exercise in the morning"
    ↓
Agent uses 6am automatically
```

Memory tracks: preferred times, frequent tasks, and behavioural patterns.

---

## ⚠️ Conflict Detection

```
New reminder: "call client at 5:00 PM"
Existing:     "team meeting at 5:10 PM"

Reply: ✅ Call client set for today at 05:00 PM
       ⚠️ Conflict: team meeting also at 5:10 PM
```

---

## 🌤️ Weather Awareness

Detects outdoor tasks (jogging, cycling, walking, picnic, etc.) and automatically fetches the weather forecast:

```
"remind me to go cycling at 7am tomorrow"

Reply: ✅ Cycling set for 12 Jun 2026 at 07:00 AM
       🌤️ Thunderstorm expected (80% rain) — consider rescheduling
```

---

## 🔔 Scheduler

A background thread checks for due reminders every 10 seconds and sends Telegram notifications with action buttons:

```
🔔 Reminder

📌 Drink water

[✅ Done]  [⏰ 10 min]  [⏰ 1 hr]
```

Recurring reminders automatically reschedule after firing.

---

## 📣 Proactive Outreach

Every day at 9 AM the agent reviews each user's schedule and sends helpful nudges if needed:

- 3+ reminders clustered in a 30-minute window → suggests spreading them out
- Outdoor reminders with bad weather forecast → suggests rescheduling
- No action needed → stays silent

---
