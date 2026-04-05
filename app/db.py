from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from app.config import DATABASE_URL

connect_args = {}
engine_args = {
    "pool_pre_ping": True,
    "pool_recycle": 300
}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # SQLite: use StaticPool (no pool_size needed)
    from sqlalchemy.pool import StaticPool
    engine_args["poolclass"] = StaticPool
else:
    # Postgres/MySQL: set pool size
    engine_args["pool_size"] = 10
    engine_args["max_overflow"] = 5

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    **engine_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()