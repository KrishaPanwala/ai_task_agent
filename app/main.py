# app/main.py
from fastapi import FastAPI, Request, Query, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from telegram import Update
from zoneinfo import ZoneInfo
import os, dateparser, asyncio
from sqlalchemy import text

from app.db import engine, SessionLocal, Base
from app.models import Task, User
from app.ai import extract_task
from app.scheduler import start_scheduler, set_main_loop
from app.telegram_bot_runner import start_telegram_bot_background
from app.telegram import send_telegram_message
from app.telegram_bot import application as telegram_app
from app.auth import (
    get_db, get_current_user, hash_password,
    verify_password, create_token
)
from sqlalchemy.orm import Session

IST = ZoneInfo("Asia/Kolkata")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# ─── Pages ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")

# ✅ Fix all template responses like this:
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(name="login.html", request=request)

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(name="register.html", request=request)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(name="index.html", request=request)

# ─── Auth Endpoints ───────────────────────────────────────────────────────────

@app.post("/register")
async def register(
    username: str = Form(...),
    password: str = Form(...),
    chat_id: str = Form(None),
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return JSONResponse({"error": "Username already exists"}, status_code=400)
    user = User(
        username=username,
        password=hash_password(password),
        chat_id=chat_id
    )
    db.add(user)
    db.commit()
    return JSONResponse({"status": "registered"})

@app.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password):
        return JSONResponse({"error": "Invalid username or password"}, status_code=401)
    token = create_token({"sub": user.username})
    response = JSONResponse({"status": "logged in"})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,
        samesite="lax"
    )
    return response

@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response

@app.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "chat_id": current_user.chat_id
    }

@app.post("/update-chat-id")
async def update_chat_id(
    chat_id: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    user.chat_id = chat_id
    db.commit()
    return JSONResponse({"status": "updated"})

# ─── Webhook ──────────────────────────────────────────────────────────────────

@app.get("/health")
@app.head("/health")
async def health():
    return {"status": "running"}

@app.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token != bot_token:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

# ─── Task Endpoints ───────────────────────────────────────────────────────────

@app.get("/extract")
async def extract(
    message: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    if not current_user.chat_id:
        return JSONResponse({"error": "Please set your Telegram Chat ID in profile"})

    result = extract_task(message)
    if "task" not in result or "time" not in result:
        return JSONResponse({"error": "Could not extract task"})

    parsed_time = dateparser.parse(result["time"], settings={
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": "Asia/Kolkata",
        "TO_TIMEZONE": "Asia/Kolkata"
    })
    if not parsed_time:
        return JSONResponse({"error": "Invalid time"})

    db = SessionLocal()
    new_task = Task(
        task=result["task"],
        time=parsed_time,
        chat_id=current_user.chat_id,
        user_id=current_user.id,
        is_recurring=result.get("is_recurring", False),
        recur_type=result.get("recur_type", None),
        recur_value=result.get("recur_value", None)
    )
    db.add(new_task)
    db.commit()
    db.close()

    try:
        recur_info = ""
        if result.get("is_recurring"):
            recur_info = f"\n🔁 Repeats: {result.get('recur_type')}"
        send_telegram_message(
            f"✅ Task Added\n\n{result['task']}\n⏰ {parsed_time.strftime('%d %b %Y at %I:%M %p')}{recur_info}",
            current_user.chat_id
        )
    except:
        pass

    return {"status": "task added"}

@app.get("/tasks")
async def get_tasks(current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    result = [
        {
            "id": t.id,
            "task": t.task,
            "time": t.time.astimezone(IST).strftime("%d %b %Y at %I:%M %p"),
            "is_recurring": t.is_recurring,
            "recur_type": t.recur_type,
            "recur_value": t.recur_value
        }
        for t in tasks
    ]
    db.close()
    return result

@app.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user)
):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if task:
        db.delete(task)
        db.commit()
    db.close()
    return {"status": "deleted"}

# ─── Startup/Shutdown ─────────────────────────────────────────────────────────

@app.on_event("startup")
async def start_services():
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS is_recurring BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS recur_type VARCHAR"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS recur_value VARCHAR"))
        conn.commit()

    set_main_loop(asyncio.get_event_loop())
    start_scheduler()
    asyncio.create_task(start_telegram_bot_background())
    print("✅ Services started successfully")

@app.on_event("shutdown")
async def shutdown_services():
    try:
        await telegram_app.stop()
        await telegram_app.shutdown()
        print("✅ Telegram bot shut down cleanly")
    except Exception as e:
        print("❌ Shutdown error:", e)