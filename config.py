import os
from dotenv import load_dotenv
import pytz

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_NAME = os.getenv("DB_NAME", "study_bot.db")
# Force timezone to UTC+5 (fixed offset to avoid timezone database issues)
# Asia/Almaty sometimes shows UTC+6 in pytz, so we use fixed UTC+5 instead
TIMEZONE_OFFSET = 5  # UTC+5 hours
TIMEZONE = pytz.FixedOffset(TIMEZONE_OFFSET * 60)  # Fixed UTC+5 timezone object

# Conversation States
TASK_NAME, TASK_TIME, TASK_PRIORITY, TASK_CATEGORY = range(4)
