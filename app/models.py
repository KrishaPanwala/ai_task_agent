# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)  # hashed
    chat_id = Column(String, nullable=True)  # Telegram chat ID
    tasks = relationship("Task", back_populates="user")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    task = Column(String, nullable=False)
    time = Column(DateTime(timezone=True), nullable=False)
    chat_id = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # ✅ link to user
    user = relationship("User", back_populates="tasks")

    # ✅ Recurring fields
    is_recurring = Column(Boolean, default=False)
    recur_type = Column(String, nullable=True)
    recur_value = Column(String, nullable=True)