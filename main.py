import logging
import json
import os
import asyncio
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
TOKEN = os.getenv("TELEGRAM_TOKEN")
SCHEDULE_FILE = "schedule.json"
SUBSCRIBERS_FILE = "subscribers.json"
TIMEZONE = pytz.timezone("Asia/Baku")

# Day mapping
DAYS_MAPPING = {
    "Monday": "Понедельник",
    "Tuesday": "Вторник",
    "Wednesday": "Среда",
    "Thursday": "Четверг",
    "Friday": "Пятница",
    "Saturday": "Суббота",
    "Sunday": "Воскресенье",
}

def load_schedule():
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return set()
    with open(SUBSCRIBERS_FILE, "r") as f:
        try:
            data = json.load(f)
            return set(data)
        except json.JSONDecodeError:
            return set()

def save_subscriber(chat_id):
    subscribers = load_subscribers()
    if chat_id not in subscribers:
        subscribers.add(chat_id)
        with open(SUBSCRIBERS_FILE, "w") as f:
            json.dump(list(subscribers), f)

def get_schedule_message_for_today():
    """Generates the schedule message for the current day."""
    now_baku = datetime.now(TIMEZONE)
    day_name_en = now_baku.strftime("%A")
    day_name_ru = DAYS_MAPPING.get(day_name_en)
    
    if not day_name_ru:
        return f"Error: Could not map day {day_name_en} to Russian."

    schedule_data = load_schedule()
    schedule_text = schedule_data.get(day_name_ru)
    
    if not schedule_text:
        return f"Сегодня {day_name_ru}:\nНет занятий."
    
    message = f"Сегодня {day_name_ru}:\n"
    
    entries = [e.strip() for e in schedule_text.split(',')]
    for entry in entries:
        if " - " in entry:
            parts = entry.split(" - ")
            if len(parts) == 2:
                name, time = parts[0], parts[1]
                message += f"{time} — {name}\n"
            else:
                message += f"{entry}\n"
        else:
            message += f"{entry}\n"
            
    return message

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and subscribes the user to the schedule."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    save_subscriber(chat_id)
    
    await update.message.reply_html(
        rf"Привет, {user.mention_html()}! Я буду отправлять тебе расписание каждый день в 08:00 по Баку. Напиши /today чтобы узнать расписание на сегодня.",
    )

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends today's schedule on command."""
    message = get_schedule_message_for_today()
    await update.message.reply_text(message)

async def send_schedule_job(application: Application):
    """Job to send the schedule."""
    message = get_schedule_message_for_today()

    subscribers = load_subscribers()
    for chat_id in subscribers:
        try:
            await application.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")

async def post_init(application: Application) -> None:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(send_schedule_job, 'cron', hour=8, minute=0, args=[application])
    scheduler.start()
    logger.info("Scheduler started")

if __name__ == "__main__":
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN not found in environment variables.")
        exit(1)

    application = Application.builder().token(TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("today", today))

    application.run_polling()
