from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path
import asyncio
import os
import dateparser

from app.db import engine, SessionLocal
from app.models import Base, Task
from app.ai import extract_task
from app.scheduler import start_scheduler
from app.telegram_bot import start_telegram_bot
from app.telegram import send_telegram_message


# -----------------------------
# FastAPI App
# -----------------------------
app = FastAPI()


# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Paths
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)


# -----------------------------
# Home Page
# -----------------------------
# -----------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.get("/health")
async def health():
    return {"status": "running"}    


# -----------------------------
# Extract Task API
# -----------------------------
@app.get("/extract")
async def extract(message: str = Query(...)):

    result = extract_task(message)

    if "task" not in result or "time" not in result:
        return JSONResponse(
            {"error": "could not extract"}
        )

    parsed_time = dateparser.parse(
        result["time"],
        settings={"PREFER_DATES_FROM": "future"}
    )

    if not parsed_time:
        return JSONResponse(
            {"error": "invalid time"}
        )

    db = SessionLocal()

    new_task = Task(
        task=result["task"],
        time=parsed_time
    )

    db.add(new_task)
    db.commit()
    db.close()

    # Send telegram notification
    try:
        send_telegram_message(
            f"✅ Task Added\n\n{result['task']}\n⏰ {parsed_time}"
        )
    except:
        pass

    return {"status": "task added"}


# -----------------------------
# Get All Tasks
# -----------------------------
@app.get("/tasks")
async def get_tasks():

    db = SessionLocal()
    tasks = db.query(Task).all()

    result = []

    for task in tasks:
        result.append({
            "id": task.id,
            "task": task.task,
            "time": str(task.time)
        })

    db.close()

    return result


# -----------------------------
# Delete Task
# -----------------------------
@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):

    db = SessionLocal()

    task = db.query(Task).filter(
        Task.id == task_id
    ).first()

    if task:
        db.delete(task)
        db.commit()

    db.close()

    return {"status": "deleted"}


# -----------------------------
# Startup Services
# -----------------------------
@app.on_event("startup")
async def start_services():

    Base.metadata.create_all(bind=engine)

    start_scheduler()

    if os.getenv("TELEGRAM_BOT_TOKEN"):
        asyncio.create_task(start_telegram_bot())

    print("✅ Services started successfully")