import asyncio
import aiosqlite
import database
from config import DB_NAME

# Weekly Schedule Data Template
# Replace with your actual schedule data
SCHEDULE_DATA = [
    # Monday
    ('MONDAY', '14:00', '🚌 Road Home', 'Low', 'Other'),
    ('MONDAY', '15:00', '🍽️ Lunch', 'Low', 'Other'),
    # Add your tasks here...
    
    # Tuesday
    ('TUESDAY', '14:00', '🚌 Road Home', 'Low', 'Other'),
    # Add your tasks here...
    
    # Add more days as needed...
]

async def run_import():
    await database.init_db()
    
    # Replace with your Telegram User ID
    USER_ID = YOUR_TELEGRAM_USER_ID_HERE
    
    print("🧹 Clearing old recurring tasks...")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM recurring_tasks")
        await db.commit()

    print("📥 Importing schedule...")
    for day, time, name, prio, cat in SCHEDULE_DATA:
        await database.add_recurring_template(USER_ID, day, name, time, prio, cat)
        print(f"   Added {day} {time}: {name}")

    print("✅ Done! Data imported. Now restart your bot and run /sync.")

if __name__ == "__main__":
    asyncio.run(run_import())
