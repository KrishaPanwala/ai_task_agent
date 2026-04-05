from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# -----------------------------
# Database URL
# -----------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./tasks.db"
)

# -----------------------------
# SQLite check
# -----------------------------
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# -----------------------------
# Engine
# -----------------------------
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10 if not DATABASE_URL.startswith("sqlite") else None
)

# -----------------------------
# Session
# -----------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# -----------------------------
# Base class
# -----------------------------
Base = declarative_base()