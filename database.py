import aiosqlite
import logging
from config import DB_NAME
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                timezone TEXT DEFAULT 'Asia/Almaty',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notification_enabled BOOLEAN DEFAULT 1
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_name TEXT,
                scheduled_time TEXT,
                priority TEXT,
                category TEXT,
                status TEXT DEFAULT 'pending',
                date TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        
        # New table for recurring templates
        await db.execute("""
            CREATE TABLE IF NOT EXISTS recurring_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                day_of_week TEXT,
                task_name TEXT,
                scheduled_time TEXT,
                priority TEXT,
                category TEXT
            )
        """)
        await db.commit()
        
        # Run migrations to add new columns and tables
        await migrate_database(db)

async def migrate_database(db):
    """Migrate database schema to support new features"""
    # Check and add columns to tasks table
    try:
        await db.execute("ALTER TABLE tasks ADD COLUMN duration INTEGER DEFAULT 0")
    except Exception:
        pass  # Column already exists
    
    try:
        await db.execute("ALTER TABLE tasks ADD COLUMN notes TEXT DEFAULT ''")
    except Exception:
        pass
    
    try:
        await db.execute("ALTER TABLE tasks ADD COLUMN tags TEXT DEFAULT ''")
    except Exception:
        pass
    
    try:
        await db.execute("ALTER TABLE tasks ADD COLUMN archived BOOLEAN DEFAULT 0")
    except Exception:
        pass
    
    try:
        await db.execute("ALTER TABLE tasks ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except Exception:
        pass
    
    try:
        await db.execute("ALTER TABLE tasks ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except Exception:
        pass
    
    # Check and add columns to users table
    try:
        await db.execute("ALTER TABLE users ADD COLUMN quiet_hours_start TEXT DEFAULT NULL")
    except Exception:
        pass
    
    try:
        await db.execute("ALTER TABLE users ADD COLUMN quiet_hours_end TEXT DEFAULT NULL")
    except Exception:
        pass
    
    try:
        await db.execute("ALTER TABLE users ADD COLUMN notification_1h BOOLEAN DEFAULT 1")
    except Exception:
        pass
    
    try:
        await db.execute("ALTER TABLE users ADD COLUMN notification_30m BOOLEAN DEFAULT 1")
    except Exception:
        pass
    
    try:
        await db.execute("ALTER TABLE users ADD COLUMN notification_start BOOLEAN DEFAULT 1")
    except Exception:
        pass
    
    # Create new tables
    await db.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            target_date TEXT,
            goal_type TEXT,
            progress INTEGER DEFAULT 0,
            target_value INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER,
            title TEXT,
            achieved BOOLEAN DEFAULT 0,
            achieved_at TIMESTAMP,
            FOREIGN KEY(goal_id) REFERENCES goals(id)
        )
    """)
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS daily_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            entry_text TEXT,
            mood TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            UNIQUE(user_id, date)
        )
    """)
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS custom_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category_name TEXT,
            emoji TEXT DEFAULT '🔹',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            UNIQUE(user_id, category_name)
        )
    """)
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS task_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            tag_name TEXT,
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        )
    """)
    
    await db.commit()

async def add_user(user_id, timezone="Asia/Almaty"):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, timezone) VALUES (?, ?)",
            (user_id, timezone)
        )
        await db.commit()

async def add_task(user_id, task_name, scheduled_time, priority, category, date_str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO tasks 
               (user_id, task_name, scheduled_time, priority, category, date) 
               VALUES (?, ?, ?, ?, ?, ?) RETURNING id""",
            (user_id, task_name, scheduled_time, priority, category, date_str)
        )
        task_id = (await cursor.fetchone())[0]
        await db.commit()
        return task_id

async def get_tasks(user_id, date_str):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND date = ? ORDER BY scheduled_time",
            (user_id, date_str)
        )
        return await cursor.fetchall()

async def update_task_status(task_id, status):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
        await db.commit()

async def add_recurring_template(user_id, day, name, time, priority, category):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """INSERT INTO recurring_tasks 
               (user_id, day_of_week, task_name, scheduled_time, priority, category) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, day, name, time, priority, category)
        )
        await db.commit()

async def generate_daily_tasks_from_recurring(user_id, target_date_obj):
    day_name = target_date_obj.strftime("%A").upper() # MONDAY, TUESDAY...
    date_str = target_date_obj.strftime("%Y-%m-%d")
    
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        # Get templates for this day of week for this user
        async with db.execute("SELECT * FROM recurring_tasks WHERE user_id = ? AND day_of_week = ?", (user_id, day_name)) as cursor:
            templates = await cursor.fetchall()
            
            created_count = 0
            for t in templates:
                # Check if already exists to prevent duplicates
                check = await db.execute(
                    "SELECT id FROM tasks WHERE user_id = ? AND date = ? AND task_name = ?",
                    (user_id, date_str, t['task_name'])
                )
                if not await check.fetchone():
                    await db.execute(
                        """INSERT INTO tasks 
                           (user_id, task_name, scheduled_time, priority, category, date, status) 
                           VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
                        (user_id, t['task_name'], t['scheduled_time'], t['priority'], t['category'], date_str)
                    )
                    created_count += 1
            
            await db.commit()
            return created_count

async def get_all_users():
    """Fetch all user IDs to schedule daily maintenance for everyone"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row['user_id'] for row in rows]

async def get_task_by_id(task_id):
    """Get a task by its ID"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return await cursor.fetchone()

async def get_pending_tasks(user_id, date_str):
    """Get all pending tasks for a user on a specific date"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND date = ? AND status = 'pending' ORDER BY scheduled_time",
            (user_id, date_str)
        )
        return await cursor.fetchall()

async def get_incomplete_tasks(user_id, date_str, current_time_str):
    """Get tasks that have passed their scheduled time but are still pending"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM tasks 
               WHERE user_id = ? AND date = ? AND status = 'pending' 
               AND scheduled_time < ? 
               ORDER BY scheduled_time""",
            (user_id, date_str, current_time_str)
        )
        return await cursor.fetchall()

async def get_user_stats(user_id, date_str):
    """Get statistics for a user: today's completion, current streak, total tasks completed"""
    import utils
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        
        # Get all today's tasks and filter out non-tasks
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND date = ?",
            (user_id, date_str)
        )
        all_today_tasks = await cursor.fetchall()
        today_tasks = utils.filter_real_tasks(all_today_tasks)
        today_total = len(today_tasks)
        today_done = sum(1 for t in today_tasks if t['status'] == 'done')
        
        # Total tasks completed (all time) - filter out non-tasks
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND status = 'done'",
            (user_id,)
        )
        all_completed = await cursor.fetchall()
        completed_tasks = utils.filter_real_tasks(all_completed)
        total_completed = len(completed_tasks)
        
        # Calculate streak (consecutive days with 100% completion)
        # Get all dates with tasks, ordered by date descending
        cursor = await db.execute(
            """SELECT date, 
                      COUNT(*) as total,
                      SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done
               FROM tasks 
               WHERE user_id = ? AND date <= ?
               GROUP BY date 
               ORDER BY date DESC""",
            (user_id, date_str)
        )
        all_days = await cursor.fetchall()
        
        streak = 0
        from datetime import datetime, timedelta
        import pytz
        from config import TIMEZONE
        # TIMEZONE is now a timezone object, not a string
        tz = TIMEZONE
        # Get UTC time first, then convert to target timezone to avoid system timezone issues
        today = datetime.now(pytz.utc).astimezone(tz).date()
        
        # For streak calculation, we need to check each day's real tasks
        for day in all_days:
            day_date = datetime.strptime(day['date'], "%Y-%m-%d").date()
            # Only count today and past days, not future
            if day_date > today:
                continue
            
            # Get tasks for this day and filter
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND date = ?",
                (user_id, day['date'])
            )
            day_tasks = await cursor.fetchall()
            real_tasks = utils.filter_real_tasks(day_tasks)
            
            if not real_tasks:
                continue  # Skip days with no real tasks
            
            real_done = sum(1 for t in real_tasks if t['status'] == 'done')
            real_total = len(real_tasks)
            
            # Skip today for streak calculation if it's not 100% complete
            if day_date == today and real_done < real_total:
                continue
            # If this day is 100% complete, increment streak
            if real_done == real_total and real_total > 0:
                streak += 1
            else:
                break
        
        return {
            'today_total': today_total,
            'today_done': today_done,
            'total_completed': total_completed,
            'streak': streak
        }

async def get_user_settings(user_id):
    """Get user settings"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()

async def toggle_notifications(user_id):
    """Toggle notification setting for a user"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Get current setting
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT notification_enabled FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            new_value = 1 if not row['notification_enabled'] else 0
            await db.execute(
                "UPDATE users SET notification_enabled = ? WHERE user_id = ?",
                (new_value, user_id)
            )
            await db.commit()
            return new_value == 1
        return None

async def get_recurring_tasks_for_day(user_id, day_of_week):
    """Get all recurring tasks for a specific day of week for a user"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM recurring_tasks WHERE user_id = ? AND day_of_week = ? ORDER BY scheduled_time",
            (user_id, day_of_week)
        )
        return await cursor.fetchall()

async def get_current_task(user_id, date_str, current_time_str):
    """Get the task that should be happening now (started within last 2 hours)"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        from datetime import datetime, timedelta
        current_dt = datetime.strptime(f"{date_str} {current_time_str}", "%Y-%m-%d %H:%M")
        # Look for tasks that started within the last 2 hours and haven't passed yet
        window_start = (current_dt - timedelta(hours=2)).strftime("%H:%M")
        
        # Get tasks that started before or at current time, but not future tasks
        cursor = await db.execute(
            """SELECT * FROM tasks 
               WHERE user_id = ? AND date = ? 
               AND scheduled_time >= ? 
               AND scheduled_time <= ? 
               AND status != 'done'
               ORDER BY scheduled_time DESC
               LIMIT 1""",
            (user_id, date_str, window_start, current_time_str)
        )
        result = await cursor.fetchone()
        
        # Double-check: make sure the task has actually started (not a future task)
        if result:
            task_time_str = result['scheduled_time']
            # If task time is after current time, it hasn't started yet - return None
            if task_time_str > current_time_str:
                return None
        return result

async def get_next_task(user_id, date_str, current_time_str):
    """Get the next upcoming task"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM tasks 
               WHERE user_id = ? AND date = ? 
               AND scheduled_time > ? 
               AND status != 'done'
               ORDER BY scheduled_time ASC
               LIMIT 1""",
            (user_id, date_str, current_time_str)
        )
        return await cursor.fetchone()

# ===== NEW FEATURES DATABASE FUNCTIONS =====

# Edit/Delete Tasks
async def update_task(task_id, task_name=None, scheduled_time=None, priority=None, category=None, duration=None, notes=None):
    """Update task fields"""
    async with aiosqlite.connect(DB_NAME) as db:
        updates = []
        params = []
        if task_name:
            updates.append("task_name = ?")
            params.append(task_name)
        if scheduled_time:
            updates.append("scheduled_time = ?")
            params.append(scheduled_time)
        if priority:
            updates.append("priority = ?")
            params.append(priority)
        if category:
            updates.append("category = ?")
            params.append(category)
        if duration is not None:
            updates.append("duration = ?")
            params.append(duration)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(task_id)
        
        if updates:
            query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
            await db.execute(query, params)
            await db.commit()

async def delete_task(task_id):
    """Delete a task"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()

# Weekly View
async def get_tasks_for_week(user_id, start_date_str):
    """Get tasks for a week starting from start_date"""
    from datetime import datetime, timedelta
    end_date = datetime.strptime(start_date_str, "%Y-%m-%d") + timedelta(days=6)
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND date >= ? AND date <= ? ORDER BY date, scheduled_time",
            (user_id, start_date_str, end_date_str)
        )
        return await cursor.fetchall()

# Enhanced Statistics
async def get_weekly_stats(user_id, start_date_str):
    """Get weekly statistics"""
    from datetime import datetime, timedelta
    end_date = datetime.strptime(start_date_str, "%Y-%m-%d") + timedelta(days=6)
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT COUNT(*) as total, SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done 
               FROM tasks WHERE user_id = ? AND date >= ? AND date <= ?""",
            (user_id, start_date_str, end_date_str)
        )
        stats = await cursor.fetchone()
        
        cursor = await db.execute(
            """SELECT category, COUNT(*) as total, SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done
               FROM tasks WHERE user_id = ? AND date >= ? AND date <= ?
               GROUP BY category""",
            (user_id, start_date_str, end_date_str)
        )
        by_category = await cursor.fetchall()
        
        return {
            'total': stats['total'] or 0,
            'done': stats['done'] or 0,
            'by_category': [dict(row) for row in by_category]
        }

async def get_monthly_stats(user_id, year, month):
    """Get monthly statistics"""
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT COUNT(*) as total, SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done 
               FROM tasks WHERE user_id = ? AND date >= ? AND date < ?""",
            (user_id, start_date, end_date)
        )
        stats = await cursor.fetchone()
        
        cursor = await db.execute(
            """SELECT date, COUNT(*) as total, SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done
               FROM tasks WHERE user_id = ? AND date >= ? AND date < ?
               GROUP BY date ORDER BY date""",
            (user_id, start_date, end_date)
        )
        daily = await cursor.fetchall()
        
        return {
            'total': stats['total'] or 0,
            'done': stats['done'] or 0,
            'daily': [dict(row) for row in daily]
        }

# Tags
async def add_tag_to_task(task_id, tag_name):
    """Add a tag to a task"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO task_tags (task_id, tag_name) VALUES (?, ?)",
            (task_id, tag_name)
        )
        await db.commit()

async def remove_tag_from_task(task_id, tag_name):
    """Remove a tag from a task"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM task_tags WHERE task_id = ? AND tag_name = ?",
            (task_id, tag_name)
        )
        await db.commit()

async def get_task_tags(task_id):
    """Get all tags for a task"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT tag_name FROM task_tags WHERE task_id = ?",
            (task_id,)
        )
        rows = await cursor.fetchall()
        return [row['tag_name'] for row in rows]

async def get_tasks_by_tag(user_id, tag_name, date_str=None):
    """Get tasks by tag"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        if date_str:
            cursor = await db.execute(
                """SELECT t.* FROM tasks t 
                   JOIN task_tags tt ON t.id = tt.task_id 
                   WHERE t.user_id = ? AND tt.tag_name = ? AND t.date = ?
                   ORDER BY t.scheduled_time""",
                (user_id, tag_name, date_str)
            )
        else:
            cursor = await db.execute(
                """SELECT t.* FROM tasks t 
                   JOIN task_tags tt ON t.id = tt.task_id 
                   WHERE t.user_id = ? AND tt.tag_name = ?
                   ORDER BY t.date, t.scheduled_time""",
                (user_id, tag_name)
            )
        return await cursor.fetchall()

# Notes/Journal
async def add_task_notes(task_id, notes):
    """Add notes to a task"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE tasks SET notes = ? WHERE id = ?", (notes, task_id))
        await db.commit()

async def add_journal_entry(user_id, date_str, entry_text, mood=None):
    """Add or update daily journal entry"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """INSERT OR REPLACE INTO daily_journal (user_id, date, entry_text, mood) 
               VALUES (?, ?, ?, ?)""",
            (user_id, date_str, entry_text, mood)
        )
        await db.commit()

async def get_journal_entry(user_id, date_str):
    """Get journal entry for a date"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM daily_journal WHERE user_id = ? AND date = ?",
            (user_id, date_str)
        )
        return await cursor.fetchone()

# Goals and Milestones
async def add_goal(user_id, title, description, target_date, goal_type, target_value=100):
    """Add a goal"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO goals (user_id, title, description, target_date, goal_type, target_value)
               VALUES (?, ?, ?, ?, ?, ?) RETURNING id""",
            (user_id, title, description, target_date, goal_type, target_value)
        )
        goal_id = (await cursor.fetchone())[0]
        await db.commit()
        return goal_id

async def get_goals(user_id, active_only=True):
    """Get goals for a user"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        if active_only:
            from datetime import datetime
            import pytz
            from config import TIMEZONE
            tz = pytz.timezone(TIMEZONE)
            # Get UTC time first, then convert to target timezone to avoid system timezone issues
            today = datetime.now(pytz.utc).astimezone(tz).strftime("%Y-%m-%d")
            cursor = await db.execute(
                "SELECT * FROM goals WHERE user_id = ? AND (target_date >= ? OR target_date IS NULL) ORDER BY target_date",
                (user_id, today)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM goals WHERE user_id = ? ORDER BY target_date",
                (user_id,)
            )
        return await cursor.fetchall()

async def update_goal_progress(goal_id, progress):
    """Update goal progress"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE goals SET progress = ? WHERE id = ?", (progress, goal_id))
        await db.commit()

async def add_milestone(goal_id, title):
    """Add a milestone to a goal"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO milestones (goal_id, title) VALUES (?, ?) RETURNING id",
            (goal_id, title)
        )
        milestone_id = (await cursor.fetchone())[0]
        await db.commit()
        return milestone_id

async def mark_milestone_achieved(milestone_id):
    """Mark a milestone as achieved"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE milestones SET achieved = 1, achieved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (milestone_id,)
        )
        await db.commit()

# Archive
async def archive_task(task_id):
    """Archive a task"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE tasks SET archived = 1 WHERE id = ?", (task_id,))
        await db.commit()

async def unarchive_task(task_id):
    """Unarchive a task"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE tasks SET archived = 0 WHERE id = ?", (task_id,))
        await db.commit()

async def get_archived_tasks(user_id, limit=50):
    """Get archived tasks"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND archived = 1 ORDER BY date DESC, scheduled_time DESC LIMIT ?",
            (user_id, limit)
        )
        return await cursor.fetchall()

# Custom Categories
async def add_custom_category(user_id, category_name, emoji='🔹'):
    """Add a custom category"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO custom_categories (user_id, category_name, emoji) VALUES (?, ?, ?)",
            (user_id, category_name, emoji)
        )
        await db.commit()

async def get_custom_categories(user_id):
    """Get custom categories for a user"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM custom_categories WHERE user_id = ? ORDER BY category_name",
            (user_id,)
        )
        return await cursor.fetchall()

# Settings
async def update_quiet_hours(user_id, start_time, end_time):
    """Update quiet hours"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET quiet_hours_start = ?, quiet_hours_end = ? WHERE user_id = ?",
            (start_time, end_time, user_id)
        )
        await db.commit()

async def update_notification_settings(user_id, notification_1h, notification_30m, notification_start):
    """Update notification settings"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """UPDATE users SET notification_1h = ?, notification_30m = ?, notification_start = ? 
               WHERE user_id = ?""",
            (notification_1h, notification_30m, notification_start, user_id)
        )
        await db.commit()

# Future dates scheduling
async def add_task_future(user_id, task_name, scheduled_time, priority, category, date_str, duration=0):
    """Add a task for a future date"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO tasks (user_id, task_name, scheduled_time, priority, category, date, duration, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending') RETURNING id""",
            (user_id, task_name, scheduled_time, priority, category, date_str, duration)
        )
        task_id = (await cursor.fetchone())[0]
        await db.commit()
        return task_id
