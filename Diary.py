import logging
from datetime import datetime, time, date
from typing import Dict

import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для FSM
(
    STATE_NONE,
    STATE_WRITING_SITUATION,
    STATE_WRITING_THOUGHTS,
    STATE_WRITING_EMOTIONS,
    STATE_WRITING_SENSATIONS,
    STATE_WRITING_ACTIONS,
    STATE_WRITING_DESIRES,
    STATE_WRITING_MEALS,
    STATE_SELECTING_REPORT_DATE,
) = range(9)


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('journal.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS journal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        situation TEXT,
        thoughts TEXT,
        emotions TEXT,
        sensations TEXT,
        actions TEXT,
        desires TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS meal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        meals_count INTEGER
    )
    ''')

    conn.commit()
    conn.close()


init_db()


def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Запись в дневник", callback_data='journal_entry')],
        [InlineKeyboardButton("🍎 Питание", callback_data='meals_entry')],
        [InlineKeyboardButton("📊 Отчёт за день", callback_data='daily_report')],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Привет! Я бот для ведения дневника.\n"
        "Используй кнопки ниже для записи или просмотра данных.",
        reply_markup=get_main_keyboard()
    )
    return STATE_NONE


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Очищаем предыдущие данные
    context.user_data.clear()

    if query.data == 'journal_entry':
        context.user_data['state'] = STATE_WRITING_SITUATION
        await query.edit_message_text("Опишите ситуацию, которую хотите записать:")
        return STATE_WRITING_SITUATION
    elif query.data == 'meals_entry':
        context.user_data['state'] = STATE_WRITING_MEALS
        await query.edit_message_text("Сколько раз вы поели сегодня?")
        return STATE_WRITING_MEALS
    elif query.data == 'daily_report':
        keyboard = [
            [InlineKeyboardButton("Сегодня", callback_data='report_today')],
            [InlineKeyboardButton("Выбрать дату", callback_data='select_date')],
            [InlineKeyboardButton("Назад", callback_data='back_to_main')]
        ]
        await query.edit_message_text(
            "За какой день вы хотите получить отчёт?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return STATE_SELECTING_REPORT_DATE
    elif query.data == 'report_today':
        today = date.today().isoformat()
        await send_daily_report(user_id, context, today)
        return STATE_NONE
    elif query.data == 'select_date':
        context.user_data['state'] = STATE_SELECTING_REPORT_DATE
        await query.edit_message_text("Введите дату в формате ГГГГ-ММ-ДД (например, 2023-11-15):")
        return STATE_SELECTING_REPORT_DATE
    elif query.data == 'back_to_main':
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=get_main_keyboard())
        return STATE_NONE
    return STATE_NONE


async def handle_journal_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id

    # Логируем текущее состояние
    current_state = context.user_data.get('state', STATE_WRITING_SITUATION)
    logger.info(f"Current state: {current_state}, User: {user_id}, Text: {text}")

    if current_state == STATE_WRITING_SITUATION:
        context.user_data['journal_entry'] = {
            'user_id': user_id,
            'date': date.today().isoformat(),
            'situation': text
        }
        context.user_data['state'] = STATE_WRITING_THOUGHTS
        await update.message.reply_text("Какие мысли у вас возникли в этой ситуации?")
        return STATE_WRITING_THOUGHTS

    elif current_state == STATE_WRITING_THOUGHTS:
        if 'journal_entry' not in context.user_data:
            context.user_data['journal_entry'] = {'user_id': user_id, 'date': date.today().isoformat()}

        context.user_data['journal_entry']['thoughts'] = text
        context.user_data['state'] = STATE_WRITING_EMOTIONS
        await update.message.reply_text("Какие эмоции вы испытывали?")
        return STATE_WRITING_EMOTIONS

    elif current_state == STATE_WRITING_EMOTIONS:
        context.user_data['journal_entry']['emotions'] = text
        context.user_data['state'] = STATE_WRITING_SENSATIONS
        await update.message.reply_text("Какие физические ощущения вы заметили?")
        return STATE_WRITING_SENSATIONS

    elif current_state == STATE_WRITING_SENSATIONS:
        context.user_data['journal_entry']['sensations'] = text
        context.user_data['state'] = STATE_WRITING_ACTIONS
        await update.message.reply_text("Что вы сделали в этой ситуации?")
        return STATE_WRITING_ACTIONS

    elif current_state == STATE_WRITING_ACTIONS:
        context.user_data['journal_entry']['actions'] = text
        context.user_data['state'] = STATE_WRITING_DESIRES
        await update.message.reply_text("Что вы хотели сделать в этой ситуации?")
        return STATE_WRITING_DESIRES

    elif current_state == STATE_WRITING_DESIRES:
        context.user_data['journal_entry']['desires'] = text

        # Сохраняем запись в базу данных
        conn = sqlite3.connect('journal.db')
        cursor = conn.cursor()
        entry = context.user_data['journal_entry']

        cursor.execute('''
        INSERT INTO journal_entries 
        (user_id, date, situation, thoughts, emotions, sensations, actions, desires)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry['user_id'],
            entry['date'],
            entry['situation'],
            entry['thoughts'],
            entry['emotions'],
            entry['sensations'],
            entry['actions'],
            entry['desires']
        ))

        conn.commit()
        conn.close()

        await update.message.reply_text(
            "Запись добавлена в дневник!",
            reply_markup=get_main_keyboard())
        return STATE_NONE

    # Если состояние неизвестно, возвращаем в главное меню
    await update.message.reply_text(
        "Что-то пошло не так. Возвращаю в главное меню.",
        reply_markup=get_main_keyboard())
    return STATE_NONE


async def handle_meals_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id

    if text.isdigit():
        meals_count = int(text)

        conn = sqlite3.connect('journal.db')
        cursor = conn.cursor()

        cursor.execute('''
        DELETE FROM meal_entries 
        WHERE user_id = ? AND date = ?
        ''', (user_id, date.today().isoformat()))

        cursor.execute('''
        INSERT INTO meal_entries (user_id, date, meals_count)
        VALUES (?, ?, ?)
        ''', (user_id, date.today().isoformat(), meals_count))

        conn.commit()
        conn.close()

        await update.message.reply_text(
            f"Записано {meals_count} приёмов пищи.",
            reply_markup=get_main_keyboard())
        return STATE_NONE
    else:
        await update.message.reply_text("Пожалуйста, введите число.")
        return STATE_WRITING_MEALS


async def handle_report_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id

    try:
        selected_date = datetime.strptime(text, '%Y-%m-%d').date().isoformat()
        await send_daily_report(user_id, context, selected_date)
        return STATE_NONE
    except ValueError:
        await update.message.reply_text(
            "Неверный формат даты. Введите дату в формате ГГГГ-ММ-ДД (например, 2023-11-15):")
        return STATE_SELECTING_REPORT_DATE


async def send_daily_report(user_id: int, context: ContextTypes.DEFAULT_TYPE, report_date: str) -> None:
    conn = sqlite3.connect('journal.db')
    cursor = conn.cursor()

    cursor.execute('''
    SELECT situation, thoughts, emotions, sensations, actions, desires
    FROM journal_entries
    WHERE user_id = ? AND date = ?
    ''', (user_id, report_date))

    journal_entries = cursor.fetchall()

    cursor.execute('''
    SELECT meals_count
    FROM meal_entries
    WHERE user_id = ? AND date = ?
    ''', (user_id, report_date))

    meal_entry = cursor.fetchone()
    conn.close()

    report_date_obj = datetime.strptime(report_date, '%Y-%m-%d').date()
    today = date.today()

    if report_date_obj == today:
        date_str = "сегодня"
    elif report_date_obj == today.replace(day=today.day - 1):
        date_str = "вчера"
    else:
        date_str = f"за {report_date_obj.strftime('%d.%m.%Y')}"

    report = f"📊 Отчёт {date_str}\n\n"

    if journal_entries:
        report += "📝 Записи дневника:\n\n"
        for i, entry in enumerate(journal_entries, 1):
            report += f"Запись #{i}:\n"
            report += f"• Ситуация: {entry[0]}\n"
            report += f"• Мысли: {entry[1]}\n"
            report += f"• Эмоции: {entry[2]}\n"
            report += f"• Ощущения: {entry[3]}\n"
            report += f"• Действия: {entry[4]}\n"
            report += f"• Желания: {entry[5]}\n\n"
    else:
        report += "📝 Записей дневника нет\n\n"

    if meal_entry:
        report += f"🍎 Питание: {meal_entry[0]} приёмов пищи\n"
    else:
        report += "🍎 Данных о питании нет\n"

    await context.bot.send_message(
        chat_id=user_id,
        text=report,
        reply_markup=get_main_keyboard()
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Действие отменено. Все несохранённые данные удалены.",
        reply_markup=get_main_keyboard()
    )
    return STATE_NONE


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Состояние сброшено. Начните заново.",
        reply_markup=get_main_keyboard()
    )
    return STATE_NONE


async def morning_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = sqlite3.connect('journal.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT user_id FROM journal_entries UNION SELECT DISTINCT user_id FROM meal_entries')
    user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    for user_id in user_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="Доброе утро! Не забудьте записать свои мысли и переживания в дневник.",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке утреннего напоминания пользователю {user_id}: {e}")


async def evening_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = sqlite3.connect('journal.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT user_id FROM journal_entries UNION SELECT DISTINCT user_id FROM meal_entries')
    user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    for user_id in user_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="Добрый вечер! Не забудьте записать приёмы пищи за сегодня.",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке вечернего напоминания пользователю {user_id}: {e}")


def main() -> None:
    application = Application.builder().token("7200943849:AAEAKQlY8wt9yFh_KX4Z1CAkOUznOD8RarU").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            STATE_NONE: [
                CallbackQueryHandler(button_handler),
            ],
            STATE_WRITING_SITUATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_journal_entry),
                CommandHandler('cancel', cancel),
            ],
            STATE_WRITING_THOUGHTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_journal_entry),
                CommandHandler('cancel', cancel),
            ],
            STATE_WRITING_EMOTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_journal_entry),
                CommandHandler('cancel', cancel),
            ],
            STATE_WRITING_SENSATIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_journal_entry),
                CommandHandler('cancel', cancel),
            ],
            STATE_WRITING_ACTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_journal_entry),
                CommandHandler('cancel', cancel),
            ],
            STATE_WRITING_DESIRES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_journal_entry),
                CommandHandler('cancel', cancel),
            ],
            STATE_WRITING_MEALS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_meals_entry),
                CommandHandler('cancel', cancel),
            ],
            STATE_SELECTING_REPORT_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_report_date_selection),
                CallbackQueryHandler(button_handler),
                CommandHandler('cancel', cancel),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('reset', reset)
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('reset', reset))

    if hasattr(application, 'job_queue') and application.job_queue:
        application.job_queue.run_daily(morning_reminder, time=time(hour=9, minute=0), days=tuple(range(7)))
        application.job_queue.run_daily(evening_reminder, time=time(hour=21, minute=0), days=tuple(range(7)))
    else:
        logger.warning("JobQueue не доступен. Напоминания не будут работать.")

    application.run_polling()


if __name__ == '__main__':
    main()