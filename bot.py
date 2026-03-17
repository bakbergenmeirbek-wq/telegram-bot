import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler

TOKEN = "8248244213:AAHik18k6bBeMytqvLYff72B-yIf9GRctCg"  # вставь сюда токен своего бота
DATA_FILE = "data.json"

# Запуск планировщика
scheduler = BackgroundScheduler()
scheduler.start()


# ------------------- Работа с JSON -------------------
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ------------------- /start и меню -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Добавить домашку", callback_data="add_homework")],
        [InlineKeyboardButton("🗓 Сегодняшние уроки", callback_data="today_schedule")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Привет! Я твой личный планер-бот 😎", reply_markup=reply_markup)


# ------------------- Обработчик кнопок -------------------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    data = load_data()

    if chat_id not in data:
        data[chat_id] = {"homework": [], "schedule": []}

    if query.data == "help":
        text = (
            "Я твой планер-бот! Вот что я умею:\n"
            "➕ Добавить домашку\n"
            "🗓 Сегодняшние уроки\n"
            "ℹ️ Помощь\n\n"
            "Также могу присылать напоминания о заданиях!"
        )
        await query.edit_message_text(text)

    elif query.data == "add_homework":
        await query.edit_message_text("Напиши домашку в формате:\nПредмет | Задание | ЧАС:МИН")
        context.user_data["adding_homework"] = True

    elif query.data == "today_schedule":
        text = "Сегодняшние домашние задания:\n"
        if data[chat_id]["homework"]:
            for hw in data[chat_id]["homework"]:
                hw_time = hw.get("time", "")
                done = "✅" if hw.get("done", False) else "❌"
                text += f"{hw['subject']} — {hw['task']} в {hw_time} {done}\n"
        else:
            text += "Пока нет заданий!"
        await query.edit_message_text(text)


# ------------------- Обработка сообщений -------------------
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    data = load_data()

    if chat_id not in data:
        data[chat_id] = {"homework": [], "schedule": []}

    if context.user_data.get("adding_homework"):
        try:
            subject, task, time_str = map(str.strip, update.message.text.split("|"))
            hour, minute = map(int, time_str.split(":"))
            data[chat_id]["homework"].append({
                "subject": subject,
                "task": task,
                "time": f"{hour:02d}:{minute:02d}",
                "done": False
            })
            save_data(data)
            await update.message.reply_text(f"Добавлено: {subject} — {task} в {hour:02d}:{minute:02d}")

            # Добавляем напоминание
            remind_time = datetime.now().replace(hour=hour, minute=minute, second=0)
            if remind_time < datetime.now():
                remind_time += timedelta(days=1)
            scheduler.add_job(send_reminder, 'date', run_date=remind_time, args=[update.message.chat_id, subject, task])

        except:
            await update.message.reply_text("Неверный формат! Используй: Предмет | Задание | ЧАС:МИН")

        context.user_data["adding_homework"] = False


# ------------------- Функция напоминания -------------------
async def send_reminder(chat_id, subject, task):
    await app.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {subject} — {task}")


# ------------------- Запуск приложения -------------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

app.run_polling()