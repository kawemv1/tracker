from telegram.ext import ContextTypes
import database
import config
from datetime import datetime, timedelta
import pytz

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    task_name = job_data['task_name']
    chat_id = job_data['chat_id']
    msg_type = job_data.get('type', 'start')
    
    # Check if it's a commute task
    is_commute = 'Commute' in task_name or '🚶' in task_name or '🚕' in task_name or '🚌' in task_name
    
    if msg_type == '1h':
        if is_commute:
            text = f"⏰ 1 hour before: {task_name}"
        else:
            text = f"⏰ 1 hour until: {task_name}"
    elif msg_type == '30m':
        if is_commute:
            text = f"⚠️ 30 minutes before: {task_name}"
        else:
            text = f"⚠️ 30 minutes until: {task_name}"
    else:
        if is_commute:
            text = f"🚀 Time to start: {task_name}"
        else:
            text = f"🚀 Time to start: {task_name}"
    
    await context.bot.send_message(chat_id=chat_id, text=text)

def schedule_task_notifications(job_queue, chat_id, task_name, task_time_obj, task_date_str):
    """Schedules 1h, 30m, and start time notifications"""
    # Combine date and time
    # We must attach timezone info to make it aware
    tz = pytz.timezone(config.TIMEZONE)
    
    task_datetime_str = f"{task_date_str} {task_time_obj.strftime('%H:%M')}"
    # Parse as naive first
    task_dt_naive = datetime.strptime(task_datetime_str, "%Y-%m-%d %H:%M")
    # Localize to Astana time
    task_dt = tz.localize(task_dt_naive)
    
    now = datetime.now(tz)
    
    # Schedule Start Time
    if task_dt > now:
        job_queue.run_once(
            send_reminder, 
            task_dt, 
            data={'chat_id': chat_id, 'task_name': task_name, 'type': 'start'}
        )
        
    # Schedule 1h before
    remind_1h = task_dt - timedelta(hours=1)
    if remind_1h > now:
        job_queue.run_once(
            send_reminder, 
            remind_1h, 
            data={'chat_id': chat_id, 'task_name': task_name, 'type': '1h'}
        )
    
    # Schedule 30m before (for all tasks including commutes)
    remind_30m = task_dt - timedelta(minutes=30)
    if remind_30m > now:
        job_queue.run_once(
            send_reminder, 
            remind_30m, 
            data={'chat_id': chat_id, 'task_name': task_name, 'type': '30m'}
        )

async def daily_maintenance(context: ContextTypes.DEFAULT_TYPE):
    """Runs every morning to generate tasks from recurring templates"""
    users = await database.get_all_users()
    tz = pytz.timezone(config.TIMEZONE)
    today = datetime.now(tz)
    
    for user_id in users:
        count = await database.generate_daily_tasks_from_recurring(user_id, today)
        if count > 0:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"☀️ Good morning! I've added {count} tasks from your recurring schedule."
            )
            # Re-fetch tasks to schedule notifications for them
            tasks = await database.get_tasks(user_id, today.strftime("%Y-%m-%d"))
            for t in tasks:
                 # Re-parse time string to object
                 t_time = datetime.strptime(t['scheduled_time'], "%H:%M").time()
                 schedule_task_notifications(
                     context.job_queue, user_id, t['task_name'], t_time, t['date']
                 )

async def regenerate_today(update, context):
    """Manual trigger via /sync command"""
    user_id = update.effective_user.id
    tz = pytz.timezone(config.TIMEZONE)
    now = datetime.now(tz)
    
    count = await database.generate_daily_tasks_from_recurring(user_id, now)
    
    # Also schedule notifications for these new tasks immediately
    if count > 0:
        tasks = await database.get_tasks(user_id, now.strftime("%Y-%m-%d"))
        for t in tasks:
                t_time = datetime.strptime(t['scheduled_time'], "%H:%M").time()
                schedule_task_notifications(
                    context.job_queue, user_id, t['task_name'], t_time, t['date']
                )

    await update.message.reply_text(f"🔄 Synced: Generated {count} tasks from your schedule.")
