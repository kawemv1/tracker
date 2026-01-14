from datetime import datetime, timedelta
import pytz
import config

def get_user_now():
    """Get current time in configured timezone"""
    tz = pytz.timezone(config.TIMEZONE)
    # Get UTC time first, then convert to target timezone to avoid system timezone issues
    utc_now = datetime.now(pytz.utc)
    return utc_now.astimezone(tz)

def get_today_str():
    return get_user_now().strftime("%Y-%m-%d")

def get_tomorrow_str():
    return (get_user_now() + timedelta(days=1)).strftime("%Y-%m-%d")

def parse_time(time_str):
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return None

def get_week_start(date_str=None):
    """Get Monday of the week for a given date"""
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        dt = get_user_now().date()
    # Monday is 0 in weekday()
    days_since_monday = dt.weekday()
    monday = dt - timedelta(days=days_since_monday)
    return monday.strftime("%Y-%m-%d")

def get_week_end(date_str=None):
    """Get Sunday of the week for a given date"""
    start = datetime.strptime(get_week_start(date_str), "%Y-%m-%d")
    end = start + timedelta(days=6)
    return end.strftime("%Y-%m-%d")

def format_week_range(date_str):
    """Format week range for display"""
    start = datetime.strptime(get_week_start(date_str), "%Y-%m-%d")
    end = start + timedelta(days=6)
    return f"{start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}"

def is_real_task(task_name):
    """Check if a task is a real task (not road, lunch, commute, rest)"""
    if not task_name:
        return False
    
    # Filter out non-tasks
    non_tasks = [
        'Road Home', '🚌 Road Home',
        'Lunch', '🍽️ Lunch',
        'Commute', '🚶 Commute', '🚕 Commute', '🚌 Commute'
    ]
    
    task_lower = task_name.lower()
    for non_task in non_tasks:
        if non_task.lower() in task_lower:
            return False
    
    return True

def filter_real_tasks(tasks):
    """Filter out non-task items from a list of tasks"""
    if not tasks:
        return []
    return [task for task in tasks if is_real_task(task['task_name'])]
