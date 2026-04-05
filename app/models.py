from sqlalchemy import Column, Integer, String, DateTime
from app.db import Base
from datetime import timezone

class Task(Base):

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    task = Column(String, nullable=False)

    # store timezone-aware UTC datetime
    time = Column(DateTime(timezone=True), nullable=False)

    chat_id = Column(String, nullable=True)