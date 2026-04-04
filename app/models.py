from sqlalchemy import Column, Integer, String, DateTime
from app.db import Base


class Task(Base):

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    task = Column(String)
    time = Column(DateTime)
    chat_id = Column(String, nullable=True)