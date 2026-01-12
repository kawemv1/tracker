# Study Accountability Bot

A Telegram bot to help you stay accountable with your study schedule and daily tasks.

## Features

- 📅 Daily task management with recurring schedules
- ⏰ Task notifications and reminders
- 📊 Statistics and progress tracking
- ✅ Mark tasks as done
- 🔔 Customizable notifications
- 📱 Easy-to-use inline keyboard interface

## Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd study_bot
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   - Copy `.env.example` to `.env`
   - Add your Telegram bot token:
     ```
     BOT_TOKEN=your_bot_token_here
     DB_NAME=study_bot.db
     ```

5. **Set up your schedule** (optional)
   - Copy `import_schedule.example.py` to `import_schedule.py`
   - Add your schedule data
   - Update `USER_ID` with your Telegram user ID
   - Run: `python import_schedule.py`

6. **Run the bot**
   ```bash
   python bot.py
   ```

## Commands

- `/start` - Start the bot and show main menu
- `/sync` - Regenerate today's tasks from recurring schedule
- `/time` - Show current time in your timezone

## Project Structure

- `bot.py` - Main bot file with handlers
- `database.py` - Database operations
- `scheduler.py` - Task scheduling and notifications
- `keyboards.py` - Inline keyboard definitions
- `utils.py` - Utility functions
- `config.py` - Configuration settings
- `import_schedule.py` - Schedule import script (not in repo)

## Notes

- The bot uses SQLite for data storage
- Timezone is set to Asia/Almaty (UTC+5) by default
- Schedule data should be kept private and not committed to the repository

## License

MIT
