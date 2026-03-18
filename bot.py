import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler

# =======================
# Настройки
# =======================
TOKEN = "8248244213:AAHik18k6bBeMytqvLYff72B-yIf9GRctCg"
DATA_FILE = "data.json"
scheduler = BackgroundScheduler()
scheduler.start()

# =======================
# Работа с JSON
# =======================
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =======================
# Главное меню
# =======================
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Добавить задачу", callback_data="add_task")],
        [InlineKeyboardButton("✅ Отметить выполненное", callback_data="done_task")],
        [InlineKeyboardButton("📅 Задачи на сегодня", callback_data="today_tasks")],
        [InlineKeyboardButton("📆 Календарь", callback_data="calendar")],
        [InlineKeyboardButton("⏰ Настроить напоминание через N дней", callback_data="set_reminder")],
    ]
    return InlineKeyboardMarkup(keyboard)

# =======================
# Команда /start
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я твой личный календарь и помощник по задачам.",
        reply_markup=main_menu_keyboard()
    )

# =======================
# Добавление задачи
# =======================
async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await update.callback_query.message.reply_text(
        "Напиши задачу и время в формате: Текст задачи | ГГГГ-ММ-ДД ЧЧ:ММ"
    )
    context.user_data['adding'] = True
    context.user_data['adding_type'] = 'normal'

# =======================
# Добавление задачи через N дней
# =======================
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text(
        "Чтобы сделать напоминание через N дней, напиши:\nТекст задачи | N"
    )
    context.user_data['adding'] = True
    context.user_data['adding_type'] = 'days'

# =======================
# Обработка сообщений
# =======================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('adding'):
        return
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {"tasks": []}

    try:
        if context.user_data.get('adding_type') == 'normal':
            text, time_str = update.message.text.split("|")
            task_time = datetime.strptime(time_str.strip(), "%Y-%m-%d %H:%M")
        else:  # через N дней
            text, days_str = update.message.text.split("|")
            days = int(days_str.strip())
            task_time = datetime.now() + timedelta(days=days)

        text = text.strip()
        task = {"text": text, "time": task_time.strftime("%Y-%m-%d %H:%M"), "done": False}
        data[user_id]["tasks"].append(task)
        save_data(data)

        # Создать напоминание
        scheduler.add_job(
            send_reminder,
            'date',
            run_date=task_time,
            kwargs={'user_id': user_id, 'task_text': text, 'context': context}
        )

        await update.message.reply_text(f"Задача добавлена: {text} в {task_time.strftime('%Y-%m-%d %H:%M')}")
    except Exception as e:
        await update.message.reply_text(f"Неверный формат! Попробуй еще раз.\nОшибка: {e}")

    context.user_data['adding'] = False
    context.user_data['adding_type'] = None

# =======================
# Отправка напоминания
# =======================
async def send_reminder(user_id, task_text, context):
    try:
        await context.bot.send_message(chat_id=int(user_id), text=f"⏰ Напоминание: {task_text}")
    except Exception as e:
        print(f"Ошибка при отправке напоминания: {e}")

# =======================
# Кнопки меню
# =======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "add_task":
        await add_task(update, context)
    elif query.data == "today_tasks":
        await show_today_tasks(update, context)
    elif query.data == "done_task":
        await mark_done(update, context)
    elif query.data == "calendar":
        await show_calendar(update, context)
    elif query.data == "set_reminder":
        await set_reminder(update, context)

# =======================
# Показ задач на сегодня
# =======================
async def show_today_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    tasks_text = ""
    if user_id in data:
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_tasks = [t for t in data[user_id]["tasks"] if t["time"].startswith(today_str)]
        if today_tasks:
            for t in today_tasks:
                status = "✅" if t["done"] else "❌"
                tasks_text += f"{status} {t['text']} в {t['time']}\n"
        else:
            tasks_text = "Нет задач на сегодня!"
    else:
        tasks_text = "Ты ещё не добавил задачи!"
    await update.callback_query.message.reply_text(tasks_text)

# =======================
# Отметка выполненного
# =======================
async def mark_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data or not data[user_id]["tasks"]:
        await update.callback_query.message.reply_text("Нет задач для отметки!")
        return

    keyboard = []
    for i, task in enumerate(data[user_id]["tasks"]):
        if not task["done"]:
            keyboard.append([InlineKeyboardButton(task["text"], callback_data=f"done_{i}")])
    if not keyboard:
        await update.callback_query.message.reply_text("Нет невыполненных задач!")
        return

    await update.callback_query.message.reply_text(
        "Выбери задачу для отметки выполненной:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data.startswith("done_"):
        index = int(query.data.split("_")[1])
        user_id = str(query.from_user.id)
        data = load_data()
        data[user_id]["tasks"][index]["done"] = True
        save_data(data)
        await query.answer("Отмечено ✅")
        await query.message.reply_text(f"Задача выполнена: {data[user_id]['tasks'][index]['text']}")

# =======================
# Календарь (просмотр задач на любой день)
# =======================
async def show_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text(
        "Напиши дату в формате ГГГГ-ММ-ДД, чтобы увидеть задачи на этот день"
    )
    context.user_data['checking_calendar'] = True

async def handle_calendar_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('checking_calendar'):
        return
    date_str = update.message.text.strip()
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except:
        await update.message.reply_text("Неверный формат даты!")
        return

    user_id = str(update.effective_user.id)
    data = load_data()
    tasks_text = ""
    if user_id in data:
        day_tasks = [t for t in data[user_id]["tasks"] if t["time"].startswith(date_str)]
        if day_tasks:
            for t in day_tasks:
                status = "✅" if t["done"] else "❌"
                tasks_text += f"{status} {t['text']} в {t['time']}\n"
        else:
            tasks_text = "Нет задач на этот день!"
    else:
        tasks_text = "Ты ещё не добавил задачи!"
    await update.message.reply_text(tasks_text)
    context.user_data['checking_calendar'] = False

# =======================
# Основной запуск
# =======================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(handle_done, pattern="^done_"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_calendar_message))

    print("Бот запущен...")
    app.run_polling()