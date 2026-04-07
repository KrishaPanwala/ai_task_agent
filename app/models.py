# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.db import Base

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    task = Column(String, nullable=False)
    time = Column(DateTime(timezone=True), nullable=False)
    chat_id = Column(String, nullable=True)

 # ✅ Recurring fields
    is_recurring = Column(Boolean, default=False)
    recur_type = Column(String, nullable=True)  # "daily", "weekly", "hourly", "interval"
    recur_value = Column(String, nullable=True)  # "monday", "60" (minutes), etc.    