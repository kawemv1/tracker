from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("⚡ What now?", callback_data='what_now')],
        [InlineKeyboardButton("✅ Today's Plan", callback_data='view_today'),
         InlineKeyboardButton("📅 Tomorrow", callback_data='view_tomorrow')],
        [InlineKeyboardButton("➕ Add Task", callback_data='add_task'),
         InlineKeyboardButton("📝 Mark Done", callback_data='mark_done')],
        [InlineKeyboardButton("❌ Incomplete", callback_data='view_incomplete'),
         InlineKeyboardButton("📊 Stats", callback_data='stats')],
        [InlineKeyboardButton("⚙️ Settings", callback_data='settings')],
        [InlineKeyboardButton("🕐 Debug: What time is it?", callback_data='debug_time')]
    ]
    return InlineKeyboardMarkup(keyboard)

def what_now_submenu_keyboard():
    keyboard = [
        [InlineKeyboardButton("⚡ What now?", callback_data='what_now')],
        [InlineKeyboardButton("🔜 What's next?", callback_data='whats_next')],
        [InlineKeyboardButton("❌ What did I miss?", callback_data='what_missed')],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_only_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]])

def time_picker_keyboard():
    times = ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]
    buttons = [InlineKeyboardButton(t, callback_data=f'time_{t}') for t in times]
    rows = [buttons[i:i+4] for i in range(0, len(buttons), 4)]
    rows.append([InlineKeyboardButton("🔙 Back", callback_data='back')])
    return InlineKeyboardMarkup(rows)

def priority_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔴 High", callback_data='prio_High'),
         InlineKeyboardButton("🟡 Medium", callback_data='prio_Medium'),
         InlineKeyboardButton("🟢 Low", callback_data='prio_Low')],
        [InlineKeyboardButton("🔙 Back", callback_data='back')]
    ]
    return InlineKeyboardMarkup(keyboard)

def category_keyboard():
    keyboard = [
        [InlineKeyboardButton("📚 IELTS", callback_data='cat_IELTS'),
         InlineKeyboardButton("🎓 SAT", callback_data='cat_SAT')],
        [InlineKeyboardButton("🏆 Olympiad", callback_data='cat_Olympiad'),
         InlineKeyboardButton("💻 Project", callback_data='cat_Project')],
        [InlineKeyboardButton("🔹 Other", callback_data='cat_Other')],
        [InlineKeyboardButton("🔙 Back", callback_data='back')]
    ]
    return InlineKeyboardMarkup(keyboard)

def mark_done_keyboard(tasks):
    """Create inline keyboard with task buttons for marking as done"""
    buttons = []
    for task in tasks:
        icon = "✅" if task['status'] == 'done' else "⬜"
        button_text = f"{icon} {task['scheduled_time']} {task['task_name'][:30]}"
        callback_data = f"done_{task['id']}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')])
    return InlineKeyboardMarkup(buttons)
