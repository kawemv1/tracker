import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_NAME = os.getenv("DB_NAME", "study_bot.db")
# Force timezone to Asia/Almaty (UTC+5) - Astana, Kazakhstan
TIMEZONE = "Asia/Almaty"  # Hardcoded to ensure correct timezone

# Conversation States
TASK_NAME, TASK_TIME, TASK_PRIORITY, TASK_CATEGORY = range(4)
