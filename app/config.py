import os
from pathlib import Path
from dotenv import load_dotenv

# -----------------------------
# Load .env
# -----------------------------
load_dotenv()

# -----------------------------
# API Keys
# -----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Optional, used for web reminders

# -----------------------------
# Database URL
# -----------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{Path(__file__).resolve().parent / 'reminders.db'}"
)

# Fix PostgreSQL URL for SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql://",
        1
    )

# -----------------------------
# Validation
# -----------------------------
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN not set")

if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY not set")

# Optional: print config on startup
print("✅ Config loaded")