from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.ai import extract_task
from app.db import engine, SessionLocal
from app.models import Base, Task
from app.scheduler import start_scheduler
from app.telegram_bot import start_telegram_bot

import dateparser
import asyncio
import os

app = FastAPI()

Base.metadata.create_all(bind=engine)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

templates = Jinja2Templates(
    directory=str(os.path.join(BASE_DIR, "templates"))
)

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static"
)

# -------------------------------
# HOME (Web Dashboard)
# -------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


# -------------------------------
# AI Task Extraction
# -------------------------------
@app.get("/extract")
def extract(message: str):

    result = extract_task(message)

    if "task" in result and "time" in result:

        parsed_time = dateparser.parse(
            result["time"],
            settings={"PREFER_DATES_FROM": "future"}
        )

        if parsed_time is None:
            return {"error": "Could not understand time"}

        db = SessionLocal()

        new_task = Task(
            task=result["task"],
            time=parsed_time
        )

        db.add(new_task)
        db.commit()
        db.close()

        return {
            "task": result["task"],
            "time": parsed_time.strftime("%I:%M %p")
        }

    return {"error": "Could not parse response"}


# -------------------------------
# GET ALL TASKS
# -------------------------------
@app.get("/tasks")
def get_tasks():

    db = SessionLocal()

    tasks = db.query(Task).order_by(Task.time).all()

    result = []

    for t in tasks:
        result.append({
            "id": t.id,
            "task": t.task,
            "time": t.time.strftime("%I:%M %p"),
            "full_time": t.time.strftime("%Y-%m-%d %H:%M:%S")
        })

    db.close()

    return result


# -------------------------------
# DELETE TASK
# -------------------------------
@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):

    db = SessionLocal()

    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        db.close()
        return {"message": "Task not found"}

    db.delete(task)
    db.commit()
    db.close()

    return {"message": "Task deleted successfully"}


# -------------------------------
# START SERVICES
# -------------------------------
@app.on_event("startup")
async def start_services():

    print("Starting Scheduler...")
    start_scheduler()

    if os.getenv("RENDER"):
        print("Starting Telegram Bot...")
        asyncio.create_task(start_telegram_bot())