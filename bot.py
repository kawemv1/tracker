import logging
import asyncio
import pytz
from datetime import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, 
    ConversationHandler, MessageHandler, filters, Defaults
)
import config
import database
import keyboards
import utils
import scheduler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def log_user_action(update_or_query, action):
    """Log user action with Telegram ID"""
    user_id = None
    if hasattr(update_or_query, 'effective_user'):
        user_id = update_or_query.effective_user.id
    elif hasattr(update_or_query, 'from_user'):
        user_id = update_or_query.from_user.id
    elif hasattr(update_or_query, 'callback_query'):
        user_id = update_or_query.callback_query.from_user.id
    
    if user_id:
        logger.info(f"[Telegram ID: {user_id}] {action}")
    else:
        logger.info(f"[SYSTEM] {action}")

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_action(update, f"User started the bot ({user.first_name})")
    await database.add_user(user.id, timezone="Asia/Almaty")
    await update.message.reply_text(
        f"👋 Hi {user.first_name}! I'm your Study Accountability Bot (Timezone: Asia/Almaty, UTC+5).",
        reply_markup=keyboards.main_menu_keyboard()
    )

async def show_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current time in configured timezone"""
    from datetime import datetime
    import pytz
    # Force Asia/Almaty timezone
    tz = pytz.timezone("Asia/Almaty")
    # Get UTC time first, then convert to target timezone to avoid system timezone issues
    utc_now = datetime.now(pytz.utc)
    now = utc_now.astimezone(tz)
    
    text = f"🕐 **Current Time**\n\n"
    text += f"📍 **Asia/Almaty (UTC+5)**: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
    text += f"🌍 **UTC**: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
    text += f"⏰ **Time Now**: {now.strftime('%H:%M')}\n"
    text += f"📅 **Date**: {now.strftime('%A, %B %d, %Y')}"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    
    try:
        log_user_action(update, f"Menu action: {query.data}")
        await query.answer()
    except Exception as e:
        logger.error(f"Error in menu_callback setup: {e}", exc_info=True)
        return
    
    if query.data == 'back_to_menu':
        await query.edit_message_text(
            "🏠 **Main Menu**", 
            parse_mode='Markdown',
            reply_markup=keyboards.main_menu_keyboard()
        )
        return

    today_str = utils.get_today_str()
    
    if query.data == 'what_now':
        from datetime import datetime
        import pytz
        tz = pytz.timezone(config.TIMEZONE)
        # Get UTC time first, then convert to target timezone to avoid system timezone issues
        now = datetime.now(pytz.utc).astimezone(tz)
        current_time_str = now.strftime("%H:%M")
        
        # Auto-generate tasks if none exist
        tasks = await database.get_tasks(query.from_user.id, today_str)
        if not tasks:
            count = await database.generate_daily_tasks_from_recurring(query.from_user.id, now)
            if count > 0:
                # Schedule notifications for new tasks
                tasks = await database.get_tasks(query.from_user.id, today_str)
                for t in tasks:
                    t_time = datetime.strptime(t['scheduled_time'], "%H:%M").time()
                    scheduler.schedule_task_notifications(
                        context.job_queue, query.from_user.id, t['task_name'], t_time, t['date']
                    )
        
        current_task = await database.get_current_task(query.from_user.id, today_str, current_time_str)
        
        if current_task:
            task_name = current_task['task_name']
            # Calculate how long the task should have been running
            task_time_str = current_task['scheduled_time']
            # Parse as naive, then convert to timezone-aware using UTC method for consistency
            task_datetime_naive = datetime.strptime(f"{today_str} {task_time_str}", "%Y-%m-%d %H:%M")
            # Use the same method as 'now' - convert via UTC to ensure consistency
            task_datetime = pytz.utc.localize(task_datetime_naive.replace(tzinfo=None)).astimezone(tz)
            duration = now - task_datetime
            duration_seconds = int(duration.total_seconds())
            
            # Only show task if it has actually started (duration >= 0)
            if duration_seconds >= 0:
                # Format duration
                hours = duration_seconds // 3600
                minutes = (duration_seconds % 3600) // 60
                
                if hours >= 1:
                    if minutes > 0:
                        duration_text = f" for {hours} hour{'s' if hours > 1 else ''} and {minutes} minute{'s' if minutes > 1 else ''}"
                    else:
                        duration_text = f" for {hours} hour{'s' if hours > 1 else ''}"
                else:
                    duration_text = f" for {minutes} minute{'s' if minutes > 1 else ''}"
                
                # Check if it's a commute task
                is_commute = 'Commute' in task_name or '🚶' in task_name or '🚕' in task_name or '🚌' in task_name
                
                if is_commute:
                    if 'Home' in task_name:
                        text = f"🔥 You should be {task_name.replace('🚶 ', '').replace('🚕 ', '').replace('🚌 ', '')}{duration_text}. Stay safe!"
                    else:
                        text = f"🔥 You should be {task_name.replace('🚶 ', '').replace('🚕 ', '').replace('🚌 ', '')}{duration_text}."
                else:
                    text = f"🔥 You should be doing: {task_name}{duration_text}"
            else:
                # Task hasn't started yet, treat as if no current task
                current_task = None
        
        if not current_task:
            # Check next task
            next_task = await database.get_next_task(query.from_user.id, today_str, current_time_str)
            if next_task:
                task_name = next_task['task_name']
                is_commute = 'Commute' in task_name or '🚶' in task_name or '🚕' in task_name or '🚌' in task_name
                if is_commute:
                    text = f"⏰ Next up: {task_name} at {next_task['scheduled_time']}"
                else:
                    text = f"⏰ Next task: {task_name} at {next_task['scheduled_time']}"
            else:
                text = "✅ No active tasks right now. Great job!"
        
        await query.edit_message_text(
            text=text,
            parse_mode='Markdown',
            reply_markup=keyboards.what_now_submenu_keyboard()
        )
    
    elif query.data == 'whats_next':
        try:
            from datetime import datetime
            import pytz
            tz = pytz.timezone(config.TIMEZONE)
            # Get UTC time first, then convert to target timezone to avoid system timezone issues
            now = datetime.now(pytz.utc).astimezone(tz)
            current_time_str = now.strftime("%H:%M")
            
            # Auto-generate tasks if none exist
            tasks = await database.get_tasks(query.from_user.id, today_str)
            if not tasks:
                count = await database.generate_daily_tasks_from_recurring(query.from_user.id, now)
                if count > 0:
                    tasks = await database.get_tasks(query.from_user.id, today_str)
                    for t in tasks:
                        t_time = datetime.strptime(t['scheduled_time'], "%H:%M").time()
                        scheduler.schedule_task_notifications(
                            context.job_queue, query.from_user.id, t['task_name'], t_time, t['date']
                        )
            
            # Get next real task (filter out non-tasks)
            all_tasks = await database.get_tasks(query.from_user.id, today_str)
            real_tasks = utils.filter_real_tasks(all_tasks)
            
            # Find next task from real tasks
            next_task = None
            for task in real_tasks:
                if task['scheduled_time'] > current_time_str and task['status'] != 'done':
                    next_task = task
                    break
            
            if next_task:
                prio_icon = "🔴" if next_task['priority'] == 'High' else "🟡" if next_task['priority'] == 'Medium' else "🟢"
                text = f"🔜 **What's Next?**\n\n"
                text += f"⏰ {next_task['scheduled_time']} {prio_icon} {next_task['task_name']}\n\n"
                
                # Calculate time until next task
                from datetime import timedelta
                task_time_naive = datetime.strptime(f"{today_str} {next_task['scheduled_time']}", "%Y-%m-%d %H:%M")
                # Use the same method as 'now' - convert via UTC to ensure consistency
                task_time = pytz.utc.localize(task_time_naive.replace(tzinfo=None)).astimezone(tz)
                time_diff = task_time - now
                
                if time_diff.total_seconds() > 0:
                    hours = int(time_diff.total_seconds() // 3600)
                    minutes = int((time_diff.total_seconds() % 3600) // 60)
                    if hours > 0:
                        text += f"⏳ In {hours}h {minutes}m"
                    else:
                        text += f"⏳ In {minutes} minutes"
            else:
                text = "✅ No more tasks scheduled for today!"
            
            await query.edit_message_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=keyboards.what_now_submenu_keyboard()
            )
        except Exception as e:
            logger.error(f"Error in whats_next: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error loading next task: {str(e)}",
                reply_markup=keyboards.what_now_submenu_keyboard()
            )
    
    elif query.data == 'what_missed':
        try:
            from datetime import datetime
            import pytz
            tz = pytz.timezone(config.TIMEZONE)
            # Get UTC time first, then convert to target timezone to avoid system timezone issues
            now = datetime.now(pytz.utc).astimezone(tz)
            current_time_str = now.strftime("%H:%M")
            
            incomplete = await database.get_incomplete_tasks(query.from_user.id, today_str, current_time_str)
            # Filter out non-tasks
            incomplete = utils.filter_real_tasks(incomplete)
            
            if not incomplete:
                text = f"✅ Great! No missed tasks today. All tasks are either done or haven't started yet."
            else:
                text = f"❌ **What did I miss?**\n\n"
                text += "*Pending tasks from earlier today:*\n\n"
                for t in incomplete:
                    prio_icon = "🔴" if t['priority'] == 'High' else "🟡" if t['priority'] == 'Medium' else "🟢"
                    text += f"⏰ {t['scheduled_time']} {prio_icon} {t['task_name']}\n"
            
            await query.edit_message_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=keyboards.what_now_submenu_keyboard()
            )
        except Exception as e:
            logger.error(f"Error in what_missed: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error loading missed tasks: {str(e)}",
                reply_markup=keyboards.what_now_submenu_keyboard()
            )
    
    elif query.data == 'view_today':
        try:
            tasks = await database.get_tasks(query.from_user.id, today_str)
            if not tasks:
                # Try to generate tasks from recurring schedule
                from datetime import datetime
                import pytz
                tz = pytz.timezone(config.TIMEZONE)
                # Get UTC time first, then convert to target timezone to avoid system timezone issues
                now = datetime.now(pytz.utc).astimezone(tz)
                count = await database.generate_daily_tasks_from_recurring(query.from_user.id, now)
                
                if count > 0:
                    # Re-fetch tasks and schedule notifications
                    tasks = await database.get_tasks(query.from_user.id, today_str)
                    for t in tasks:
                        t_time = datetime.strptime(t['scheduled_time'], "%H:%M").time()
                        scheduler.schedule_task_notifications(
                            context.job_queue, query.from_user.id, t['task_name'], t_time, t['date']
                        )
                    # Filter out non-tasks
                    tasks = utils.filter_real_tasks(tasks)
                    if tasks:
                        text = f"📅 **Today's Plan ({today_str}):**\n\n"
                        text += f"_Generated {len(tasks)} tasks from your schedule_\n\n"
                        for t in tasks:
                            icon = "✅" if t['status'] == 'done' else "⬜"
                            prio_icon = "🔴" if t['priority'] == 'High' else "🟡" if t['priority'] == 'Medium' else "🟢"
                            text += f"{icon} {t['scheduled_time']} {prio_icon} {t['task_name']}\n"
                    else:
                        text = f"📅 No tasks scheduled for today ({today_str})."
                else:
                    text = f"📅 No tasks scheduled for today ({today_str}).\n\n"
                    text += "💡 Run /sync to generate tasks from your recurring schedule, or use '➕ Add Task' to add one manually."
            else:
                # Filter out non-tasks
                tasks = utils.filter_real_tasks(tasks)
                if not tasks:
                    text = f"📅 No tasks scheduled for today ({today_str})."
                else:
                    text = f"📅 **Today's Plan ({today_str}):**\n\n"
                    for t in tasks:
                        icon = "✅" if t['status'] == 'done' else "⬜"
                        prio_icon = "🔴" if t['priority'] == 'High' else "🟡" if t['priority'] == 'Medium' else "🟢"
                        text += f"{icon} {t['scheduled_time']} {prio_icon} {t['task_name']}\n"
            
            await query.edit_message_text(
                text=text, 
                parse_mode='Markdown', 
                reply_markup=keyboards.back_only_keyboard()
            )
        except Exception as e:
            logger.error(f"Error in view_today: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error loading today's plan: {str(e)}",
                reply_markup=keyboards.back_only_keyboard()
            )
    
    elif query.data == 'mark_done':
        try:
            tasks = await database.get_tasks(query.from_user.id, today_str)
            # Filter out non-tasks
            tasks = utils.filter_real_tasks(tasks)
            if not tasks:
                await query.edit_message_text(
                    f"📝 No tasks found for today ({today_str}).",
                    reply_markup=keyboards.back_only_keyboard()
                )
            else:
                text = f"📝 **Mark tasks as done ({today_str}):**\n\nClick on a task to mark it as complete.\n"
                await query.edit_message_text(
                    text=text,
                    parse_mode='Markdown',
                    reply_markup=keyboards.mark_done_keyboard(tasks)
                )
        except Exception as e:
            logger.error(f"Error in mark_done: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error loading tasks: {str(e)}",
                reply_markup=keyboards.back_only_keyboard()
            )
    
    elif query.data == 'stats':
        try:
            stats = await database.get_user_stats(query.from_user.id, today_str)
            if stats:
                text = f"📊 **Your Statistics**\n\n"
                text += f"📅 Today: {stats['today_done']}/{stats['today_total']} tasks done\n"
                text += f"🔥 Current Streak: {stats['streak']} days\n"
                text += f"🎯 Total Completed: {stats['total_completed']} tasks"
            else:
                text = "📊 **Your Statistics**\n\nNo statistics available yet."
            
            await query.edit_message_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=keyboards.back_only_keyboard()
            )
        except Exception as e:
            logger.error(f"Error in stats: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error loading statistics: {str(e)}",
                reply_markup=keyboards.back_only_keyboard()
            )
    
    elif query.data == 'view_tomorrow':
        try:
            tomorrow_str = utils.get_tomorrow_str()
            tasks = await database.get_tasks(query.from_user.id, tomorrow_str)
            
            if not tasks:
                # Generate preview from recurring_tasks
                from datetime import datetime, timedelta
                import pytz
                tz = pytz.timezone(config.TIMEZONE)
                # Get UTC time first, then convert to target timezone to avoid system timezone issues
                today = datetime.now(pytz.utc).astimezone(tz)
                tomorrow = today + timedelta(days=1)
                day_name = tomorrow.strftime("%A").upper()  # MONDAY, TUESDAY...
                recurring = await database.get_recurring_tasks_for_day(query.from_user.id, day_name)
                
                if recurring:
                    # Filter out non-tasks
                    recurring = utils.filter_real_tasks(recurring)
                    if recurring:
                        text = f"📅 **Tomorrow's Preview ({tomorrow_str}):**\n\n"
                        text += "*Based on your recurring schedule:*\n\n"
                        for t in recurring:
                            text += f"⏰ {t['scheduled_time']} {t['task_name']}\n"
                    else:
                        text = f"📅 No tasks scheduled for tomorrow ({tomorrow_str})."
                else:
                    text = f"📅 No tasks scheduled for tomorrow ({tomorrow_str})."
            else:
                # Filter out non-tasks
                tasks = utils.filter_real_tasks(tasks)
                if not tasks:
                    text = f"📅 No tasks scheduled for tomorrow ({tomorrow_str})."
                else:
                    text = f"📅 **Tomorrow's Plan ({tomorrow_str}):**\n\n"
                    for t in tasks:
                        icon = "✅" if t['status'] == 'done' else "⬜"
                        prio_icon = "🔴" if t['priority'] == 'High' else "🟡" if t['priority'] == 'Medium' else "🟢"
                        text += f"{icon} {t['scheduled_time']} {prio_icon} {t['task_name']}\n"
            
            await query.edit_message_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=keyboards.back_only_keyboard()
            )
        except Exception as e:
            logger.error(f"Error in view_tomorrow: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error loading tomorrow's plan: {str(e)}",
                reply_markup=keyboards.back_only_keyboard()
            )
    
    elif query.data == 'view_incomplete':
        try:
            from datetime import datetime
            import pytz
            tz = pytz.timezone(config.TIMEZONE)
            # Get UTC time first, then convert to target timezone to avoid system timezone issues
            now = datetime.now(pytz.utc).astimezone(tz)
            current_time_str = now.strftime("%H:%M")
            
            incomplete = await database.get_incomplete_tasks(query.from_user.id, today_str, current_time_str)
            # Filter out non-tasks
            incomplete = utils.filter_real_tasks(incomplete)
            
            if not incomplete:
                text = f"✅ Great! No missed tasks today. All tasks are either done or haven't started yet."
            else:
                text = f"❌ **Missed/Incomplete Tasks ({today_str}):**\n\n"
                text += "*Tasks that have passed their start time but are still pending:*\n\n"
                for t in incomplete:
                    prio_icon = "🔴" if t['priority'] == 'High' else "🟡" if t['priority'] == 'Medium' else "🟢"
                    text += f"⏰ {t['scheduled_time']} {prio_icon} {t['task_name']}\n"
            
            await query.edit_message_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=keyboards.back_only_keyboard()
            )
        except Exception as e:
            logger.error(f"Error in view_incomplete: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error loading incomplete tasks: {str(e)}",
                reply_markup=keyboards.back_only_keyboard()
            )
    
    elif query.data == 'settings':
        settings = await database.get_user_settings(query.from_user.id)
        if settings:
            notif_status = "✅ ON" if settings['notification_enabled'] else "❌ OFF"
            text = f"⚙️ **Settings**\n\n"
            text += f"🔔 Notifications: {notif_status}\n\n"
            text += "Click below to toggle notifications:"
            
            toggle_text = "🔕 Turn OFF" if settings['notification_enabled'] else "🔔 Turn ON"
            keyboard = [
                [InlineKeyboardButton(toggle_text, callback_data='toggle_notifications')],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
            ]
            await query.edit_message_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(
                "❌ Error loading settings.",
                reply_markup=keyboards.back_only_keyboard()
            )
    
    elif query.data == 'toggle_notifications':
        new_status = await database.toggle_notifications(query.from_user.id)
        if new_status is not None:
            status_text = "✅ ON" if new_status else "❌ OFF"
            text = f"⚙️ **Settings**\n\n"
            text += f"🔔 Notifications: {status_text}\n\n"
            text += "Click below to toggle notifications:"
            
            toggle_text = "🔕 Turn OFF" if new_status else "🔔 Turn ON"
            keyboard = [
                [InlineKeyboardButton(toggle_text, callback_data='toggle_notifications')],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
            ]
            await query.edit_message_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.answer("❌ Error toggling notifications.", show_alert=True)
    
    elif query.data == 'debug_time':
        from datetime import datetime
        import pytz
        
        tz = pytz.timezone(config.TIMEZONE)
        # Get UTC time first, then convert to target timezone
        utc_now = datetime.now(pytz.utc)
        local_now = utc_now.astimezone(tz)
        
        # Also get system time for comparison
        system_now = datetime.now()
        
        text = f"🕐 **Debug: Current Time**\n\n"
        text += f"📍 **Configured Timezone**: {config.TIMEZONE}\n"
        text += f"🌍 **UTC Time**: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        text += f"📍 **Local Time ({tz})**: {local_now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        text += f"⏰ **Time Display**: {local_now.strftime('%H:%M')}\n"
        text += f"📅 **Date**: {local_now.strftime('%A, %B %d, %Y')}\n\n"
        text += f"💻 **System Local Time**: {system_now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        text += f"🔧 **UTC Offset**: {local_now.utcoffset()}\n"
        text += f"🌐 **Timezone Name**: {local_now.tzname()}\n\n"
        text += f"📊 **Time Calculation Method**:\n"
        text += f"`datetime.now(pytz.utc).astimezone(tz)`"
        
        await query.edit_message_text(
            text=text,
            parse_mode='Markdown',
            reply_markup=keyboards.back_only_keyboard()
        )
    
    elif query.data.startswith('done_'):
        try:
            # Mark task as done
            task_id = int(query.data.split('_')[1])
            await database.update_task_status(task_id, 'done')
            
            # Refresh the mark_done list
            tasks = await database.get_tasks(query.from_user.id, today_str)
            # Filter out non-tasks
            tasks = utils.filter_real_tasks(tasks)
            text = f"📝 **Mark tasks as done ({today_str}):**\n\nClick on a task to mark it as complete.\n"
            await query.edit_message_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=keyboards.mark_done_keyboard(tasks)
            )
            await query.answer("✅ Task marked as done!")
        except Exception as e:
            logger.error(f"Error marking task as done: {e}", exc_info=True)
            await query.answer("❌ Error marking task as done.", show_alert=True)

# --- Add Task Conversation ---
async def start_add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✍️ Enter task name:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data='cancel_add')]])
    )
    return config.TASK_NAME

async def receive_task_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_task_name'] = update.message.text
    await update.message.reply_text(
        f"⏰ Select start time (Astana Time) or type HH:MM:", 
        reply_markup=keyboards.time_picker_keyboard()
    )
    return config.TASK_TIME

async def back_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✍️ Enter task name:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data='cancel_add')]])
    )
    return config.TASK_NAME

async def receive_task_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    time_obj = utils.parse_time(text)
    if not time_obj:
        await update.message.reply_text("❌ Invalid format. Use HH:MM (e.g., 15:30)")
        return config.TASK_TIME
    
    context.user_data['new_task_time'] = time_obj
    await update.message.reply_text("🔥 Select Priority:", reply_markup=keyboards.priority_keyboard())
    return config.TASK_PRIORITY

async def task_time_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_str = query.data.split('_')[1]
    context.user_data['new_task_time'] = utils.parse_time(time_str)
    
    await query.edit_message_text("🔥 Select Priority:", reply_markup=keyboards.priority_keyboard())
    return config.TASK_PRIORITY

async def back_to_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⏰ Select start time (Astana Time) or type HH:MM:", 
        reply_markup=keyboards.time_picker_keyboard()
    )
    return config.TASK_TIME

async def receive_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    priority = query.data.split('_')[1]
    context.user_data['new_task_priority'] = priority
    
    await query.edit_message_text("📂 Select Category:", reply_markup=keyboards.category_keyboard())
    return config.TASK_CATEGORY

async def back_to_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔥 Select Priority:", reply_markup=keyboards.priority_keyboard())
    return config.TASK_PRIORITY

async def receive_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split('_')[1]
    
    user_id = query.from_user.id
    name = context.user_data['new_task_name']
    time_obj = context.user_data['new_task_time']
    time_str = time_obj.strftime("%H:%M")
    prio = context.user_data['new_task_priority']
    date_str = utils.get_today_str()
    
    await database.add_task(user_id, name, time_str, prio, category, date_str)
    
    # Schedule for Today
    scheduler.schedule_task_notifications(
        context.job_queue, user_id, name, time_obj, date_str
    )
    
    await query.edit_message_text(
        f"✅ Added: *{name}* at {time_str} ({prio})\nTo: {category}",
        parse_mode='Markdown'
    )
    await context.bot.send_message(
        chat_id=user_id, 
        text="What's next?", 
        reply_markup=keyboards.main_menu_keyboard()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Action cancelled.")
        await update.callback_query.message.reply_text("🏠 Main Menu", reply_markup=keyboards.main_menu_keyboard())
    else:
        await update.message.reply_text("❌ Action cancelled.", reply_markup=keyboards.main_menu_keyboard())
    return ConversationHandler.END

# --- Main Setup ---
def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(database.init_db())

    # Set timezone for all operations - Force Asia/Almaty (UTC+5)
    astana_tz = pytz.timezone("Asia/Almaty")
    defaults = Defaults(tzinfo=astana_tz)
    application = ApplicationBuilder().token(config.BOT_TOKEN).defaults(defaults).build()
    
    # Explicitly configure scheduler timezone
    application.job_queue.scheduler.configure(timezone=astana_tz)
    
    # Verify timezone is set correctly
    from datetime import datetime
    test_utc = datetime.now(pytz.utc)
    test_local = test_utc.astimezone(astana_tz)
    print(f"✅ Timezone configured: {astana_tz}")
    print(f"✅ Config TIMEZONE: {config.TIMEZONE}")
    print(f"✅ Current UTC time: {test_utc.strftime('%H:%M:%S')}")
    print(f"✅ Current local time: {test_local.strftime('%H:%M:%S')}")

    # Conversation Handler
    add_task_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_task, pattern='^add_task$')],
        states={
            config.TASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_task_name),
                CallbackQueryHandler(cancel, pattern='^cancel_add$')
            ],
            config.TASK_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_task_time),
                CallbackQueryHandler(task_time_button, pattern='^time_'),
                CallbackQueryHandler(back_to_name, pattern='^back$')
            ],
            config.TASK_PRIORITY: [
                CallbackQueryHandler(receive_priority, pattern='^prio_'),
                CallbackQueryHandler(back_to_time, pattern='^back$')
            ],
            config.TASK_CATEGORY: [
                CallbackQueryHandler(receive_category, pattern='^cat_'),
                CallbackQueryHandler(back_to_priority, pattern='^back$')
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("sync", scheduler.regenerate_today))
    application.add_handler(CommandHandler("time", show_time))
    application.add_handler(add_task_conv)
    application.add_handler(CallbackQueryHandler(menu_callback))

    # Run Daily Maintenance at 04:00 AM Astana time
    # timezone is automatically used from scheduler configuration and bot defaults
    application.job_queue.run_daily(scheduler.daily_maintenance, time=time(4, 0))

    print(f"🤖 Bot is running in {config.TIMEZONE}...")
    application.run_polling()

if __name__ == '__main__':
    main()
