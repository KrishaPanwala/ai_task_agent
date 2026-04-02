from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

from app.ai import extract_task
from app.db import SessionLocal
from app.models import Task
from app.config import TELEGRAM_BOT_TOKEN

import dateparser


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_message = update.message.text

    result = extract_task(user_message)

    if "task" in result and "time" in result:

        parsed_time = dateparser.parse(
            result["time"],
            settings={"PREFER_DATES_FROM": "future"}
        )

        if parsed_time is None:
            await update.message.reply_text("❌ Could not understand time")
            return

        db = SessionLocal()

        new_task = Task(
            task=result["task"],
            time=parsed_time
        )

        db.add(new_task)
        db.commit()
        db.close()

        await update.message.reply_text(
            f"✅ Task scheduled\n\nTask: {result['task']}\nTime: {parsed_time.strftime('%I:%M %p')}"
        )

    else:
        await update.message.reply_text("❌ Could not understand task")


async def start_telegram_bot():

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("Telegram bot running...")

    await application.initialize()
    await application.start()

    # remove webhook and old sessions
    await application.bot.delete_webhook(drop_pending_updates=True)

    await application.updater.start_polling()