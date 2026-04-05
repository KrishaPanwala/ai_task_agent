# app/main.py
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os, dateparser, asyncio

from app.db import engine, SessionLocal, Base
from app.models import Task
from app.ai import extract_task
from app.scheduler import start_scheduler
from app.telegram_bot_runner import start_telegram_bot_background
from app.telegram import send_telegram_message

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
@app.head("/health")
async def health():
    return {"status": "running"}

@app.get("/extract")
async def extract(message: str = Query(...)):
    result = extract_task(message)
    if "task" not in result or "time" not in result:
        return JSONResponse({"error": "could not extract"})
    parsed_time = dateparser.parse(result["time"], settings={"PREFER_DATES_FROM": "future"})
    if not parsed_time:
        return JSONResponse({"error": "invalid time"})
    db = SessionLocal()
    new_task = Task(task=result["task"], time=parsed_time, chat_id=os.getenv("TELEGRAM_CHAT_ID"))
    db.add(new_task)
    db.commit()
    db.close()
    try:
        send_telegram_message(f"✅ Task Added\n\n{result['task']}\n⏰ {parsed_time}", os.getenv("TELEGRAM_CHAT_ID"))
    except:
        pass
    return {"status": "task added"}

@app.get("/tasks")
async def get_tasks():
    db = SessionLocal()
    tasks = db.query(Task).all()
    result = [{"id": t.id, "task": t.task, "time": str(t.time)} for t in tasks]
    db.close()
    return result

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
    db.close()
    return {"status": "deleted"}

@app.on_event("startup")
async def start_services():
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    asyncio.create_task(start_telegram_bot_background())
    print("✅ Services started successfully")