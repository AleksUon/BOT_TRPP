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
    STATE_WRITING_MEALS_COUNT,  # Состояние для ввода количества приемов пищи
    STATE_WRITING_MEALS_COMMENT,  # Новое состояние для комментариев о питании
    STATE_SELECTING_REPORT_DATE,
) = range(10)


def init_db():
    conn = sqlite3.connect('journal.db')
    cursor = conn.cursor()

    # Создаем таблицу для записей дневника
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

    # Создаем таблицу для записей о питании с проверкой существования столбца
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS meal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        meals_count INTEGER,
        comments TEXT
    )
    ''')

    # Проверяем существование столбца comments и добавляем его если нужно
    cursor.execute("PRAGMA table_info(meal_entries)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'comments' not in columns:
        cursor.execute("ALTER TABLE meal_entries ADD COLUMN comments TEXT")

    conn.commit()
    conn.close()


init_db()


def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Запись в дневник", callback_data='journal_entry')],
        [InlineKeyboardButton("🍎 Питание", callback_data='meals_entry')],
        [InlineKeyboardButton("📊 Отчёт за день", callback_data='daily_report')],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data='help')],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_emotions_keyboard():
    # Расширенный список эмоций сгруппированных по категориям
    emotions_groups = {
        "😊 Положительные": [
            "Радость", "Счастье", "Удовлетворение", "Восторг",
            "Любовь", "Благодарность", "Гордость", "Надежда",
            "Вдохновение", "Умиротворение", "Уверенность", "Волнение"
        ],
        "😢 Отрицательные": [
            "Грусть", "Злость", "Страх", "Разочарование",
            "Тревога", "Стресс", "Вина", "Стыд",
            "Обида", "Отчаяние", "Одиночество", "Зависть"
        ],
        "😐 Нейтральные": [
            "Удивление", "Любопытство", "Равнодушие",
            "Скука", "Задумчивость", "Неопределенность"
        ],
        "💪 Энергичные": [
            "Энтузиазм", "Решимость", "Азарт",
            "Драйв", "Мотивация", "Сосредоточенность"
        ],
        "😴 Усталые": [
            "Усталость", "Апатия", "Изнеможение",
            "Сонливость", "Расслабленность", "Истощение"
        ]
    }

    keyboard = []

    # Создаем кнопки для каждой группы эмоций
    for group_name, emotions in emotions_groups.items():
        # Добавляем заголовок группы
        keyboard.append([InlineKeyboardButton(group_name, callback_data=f"emotion_group_{group_name[2:]}")])

        # Разбиваем эмоции на ряды по 3 кнопки
        row = []
        for i, emotion in enumerate(emotions, 1):
            row.append(InlineKeyboardButton(f"{emotion}", callback_data=f"emotion_{emotion}"))
            if i % 3 == 0 or i == len(emotions):
                keyboard.append(row)
                row = []

    # Добавляем кнопку для завершения выбора
    keyboard.append([
        InlineKeyboardButton("✅ Готово", callback_data="emotions_done")
    ])

    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Привет! Я бот для ведения дневника.\n"
        "Используй кнопки ниже для записи или просмотра данных.",
        reply_markup=get_main_keyboard()
    )
    return STATE_NONE

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
    📝 <b>Доступные команды:</b>

    /start - Начать работу с ботом
    /help - Показать это сообщение
    /cancel - Отменить текущее действие
    /reset - Сбросить состояние

    <b>Основные функции:</b>
    - 📝 Запись в дневник - записывайте свои мысли и переживания
    - 🍎 Питание - отслеживайте приемы пищи
    - 📊 Отчёт за день - просматривайте свои записи

    Выберите нужный пункт в меню или используйте команды.
    """

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(help_text, parse_mode='HTML', reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text(help_text, parse_mode='HTML', reply_markup=get_main_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == 'journal_entry':
        context.user_data.clear()
        context.user_data['state'] = STATE_WRITING_SITUATION
        await query.edit_message_text("Опишите ситуацию, которую хотите записать:")
        return STATE_WRITING_SITUATION
    elif query.data == 'meals_entry':
        context.user_data.clear()
        context.user_data['state'] = STATE_WRITING_MEALS_COUNT  # Изменено на STATE_WRITING_MEALS_COUNT
        await query.edit_message_text("Сколько раз вы поели сегодня?")
        return STATE_WRITING_MEALS_COUNT
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
    elif query.data == 'help':
        await help_command(update, context)
        return STATE_NONE
    elif query.data.startswith('emotion_'):
        emotion = query.data.split('_')[1]
        if 'selected_emotions' not in context.user_data:
            context.user_data['selected_emotions'] = []

        if emotion in context.user_data['selected_emotions']:
            context.user_data['selected_emotions'].remove(emotion)
        else:
            context.user_data['selected_emotions'].append(emotion)

        # Обновляем сообщение с текущим списком выбранных эмоций
        selected = ", ".join(
            context.user_data['selected_emotions']) if 'selected_emotions' in context.user_data else "пока ничего"
        await query.edit_message_text(
            text=f"Выберите эмоции (выбрано: {selected}):",
            reply_markup=get_emotions_keyboard())
        return STATE_WRITING_EMOTIONS
    elif query.data == 'emotions_done':
        if 'selected_emotions' in context.user_data and context.user_data['selected_emotions']:
            emotions_text = ", ".join(context.user_data['selected_emotions'])
            context.user_data['journal_entry']['emotions'] = emotions_text
            await query.edit_message_text(f"Выбранные эмоции: {emotions_text}")

            context.user_data['state'] = STATE_WRITING_SENSATIONS
            await context.bot.send_message(
                chat_id=user_id,
                text="Какие физические ощущения вы заметили?")
            return STATE_WRITING_SENSATIONS
        else:
            await query.answer("Пожалуйста, выберите хотя бы одну эмоцию")
            return STATE_WRITING_EMOTIONS
    elif query.data.startswith('emotion_group_'):
        # Просто подтверждаем выбор группы (можно добавить логику если нужно)
        await query.answer(f"Группа эмоций: {query.data.split('_')[2]}")
        return STATE_WRITING_EMOTIONS

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

        # Предлагаем выбрать эмоции из списка
        await update.message.reply_text(
            "Выберите эмоции из списка:",
            reply_markup=get_emotions_keyboard())
        return STATE_WRITING_EMOTIONS

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
    """Обработчик ввода данных о питании"""
    user = update.message.from_user
    text = update.message.text
    user_id = user.id

    if context.user_data.get('state') == STATE_WRITING_MEALS_COUNT:
        # Этап ввода количества приемов пищи
        if text.isdigit():
            meals_count = int(text)
            context.user_data['meals_count'] = meals_count
            context.user_data['state'] = STATE_WRITING_MEALS_COMMENT

            # Запрашиваем комментарии о питании
            await update.message.reply_text(
                "Хотите добавить комментарии о своем питании сегодня? "
                "(Например, что ели, как себя чувствовали после еды и т.д.)\n"
                "Можно просто написать 'нет', если не хотите оставлять комментарий."
            )
            return STATE_WRITING_MEALS_COMMENT
        else:
            await update.message.reply_text("Пожалуйста, введите число.")
            return STATE_WRITING_MEALS_COUNT

    elif context.user_data.get('state') == STATE_WRITING_MEALS_COMMENT:
        # Этап ввода комментариев о питании
        comments = text if text.lower() != 'нет' else None
        meals_count = context.user_data['meals_count']

        conn = sqlite3.connect('journal.db')
        cursor = conn.cursor()

        # Удаляем старую запись за сегодня, если есть
        cursor.execute('''
        DELETE FROM meal_entries 
        WHERE user_id = ? AND date = ?
        ''', (user_id, date.today().isoformat()))

        # Добавляем новую запись с комментарием
        cursor.execute('''
        INSERT INTO meal_entries (user_id, date, meals_count, comments)
        VALUES (?, ?, ?, ?)
        ''', (user_id, date.today().isoformat(), meals_count, comments))

        conn.commit()
        conn.close()

        # Формируем ответ пользователю
        response = f"Записано {meals_count} приёмов пищи."
        if comments:
            response += f"\n\nВаши комментарии:\n{comments}"

        await update.message.reply_text(
            response,
            reply_markup=get_main_keyboard())

        # Очищаем временные данные
        del context.user_data['meals_count']
        return STATE_NONE

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

# Отправка отчета, чтобы показывать комментарии о питании
async def send_daily_report(user_id: int, context: ContextTypes.DEFAULT_TYPE, report_date: str) -> None:
    conn = sqlite3.connect('journal.db')
    cursor = conn.cursor()

    # Получаем записи дневника
    cursor.execute('''
    SELECT situation, thoughts, emotions, sensations, actions, desires
    FROM journal_entries
    WHERE user_id = ? AND date = ?
    ''', (user_id, report_date))
    journal_entries = cursor.fetchall()

    # Получаем данные о питании (теперь включая комментарии)
    cursor.execute('''
    SELECT meals_count, comments
    FROM meal_entries
    WHERE user_id = ? AND date = ?
    ''', (user_id, report_date))
    meal_entry = cursor.fetchone()
    conn.close()

    # Форматируем дату для отчета
    report_date_obj = datetime.strptime(report_date, '%Y-%m-%d').date()
    today = date.today()

    if report_date_obj == today:
        date_str = "сегодня"
    elif report_date_obj == today.replace(day=today.day - 1):
        date_str = "вчера"
    else:
        date_str = f"за {report_date_obj.strftime('%d.%m.%Y')}"

    # Формируем отчет
    report = f"📊 Отчёт {date_str}\n\n"

    # Добавляем записи дневника
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

    # Добавляем информацию о питании с комментариями
    if meal_entry:
        report += f"🍎 Питание: {meal_entry[0]} приёмов пищи\n"
        if meal_entry[1]:  # Если есть комментарии
            report += f"📝 Комментарии о питании:\n{meal_entry[1]}\n"
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
                CommandHandler('help', help_command),
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
                CallbackQueryHandler(button_handler),
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
            STATE_WRITING_MEALS_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_meals_entry),
                CommandHandler('cancel', cancel),
            ],
            STATE_WRITING_MEALS_COMMENT: [
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
            CommandHandler('reset', reset),
            CommandHandler('help', help_command),
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('reset', reset))
    application.add_handler(CommandHandler('help', help_command))

    if hasattr(application, 'job_queue') and application.job_queue:
        application.job_queue.run_daily(morning_reminder, time=time(hour=9, minute=0), days=tuple(range(7)))
        application.job_queue.run_daily(evening_reminder, time=time(hour=21, minute=0), days=tuple(range(7)))
    else:
        logger.warning("JobQueue не доступен. Напоминания не будут работать.")

    application.run_polling()

if __name__ == '__main__':
    main()