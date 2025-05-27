import logging
from datetime import time
from typing import Dict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
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
) = range(8)

# Хранение данных пользователей
user_data: Dict[int, Dict] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.message.from_user
    user_data[user.id] = {
        'state': STATE_NONE,
        'journal_entry': {},
        'meals_entry': None,
    }

    await update.message.reply_text(
        "Привет! Я бот для ведения дневника.\n"
        "Используй кнопки ниже для записи или просмотра данных.",
        reply_markup=get_main_keyboard()
    )


def get_main_keyboard():
    """Возвращает основную клавиатуру"""
    keyboard = [
        [InlineKeyboardButton("📝 Запись в дневник", callback_data='journal_entry')],
        [InlineKeyboardButton("🍎 Питание", callback_data='meals_entry')],
        [InlineKeyboardButton("📊 Отчёт за день", callback_data='daily_report')],
    ]
    return InlineKeyboardMarkup(keyboard)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_data:
        user_data[user_id] = {
            'state': STATE_NONE,
            'journal_entry': {},
            'meals_entry': None,
        }

    if query.data == 'journal_entry':
        user_data[user_id]['state'] = STATE_WRITING_SITUATION
        await query.edit_message_text("Опишите ситуацию, которую хотите записать:")
    elif query.data == 'meals_entry':
        user_data[user_id]['state'] = STATE_WRITING_MEALS
        await query.edit_message_text("Сколько раз вы поели сегодня?")
    elif query.data == 'daily_report':
        await send_daily_report(user_id, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений"""
    user = update.message.from_user
    text = update.message.text

    if user.id not in user_data:
        user_data[user.id] = {
            'state': STATE_NONE,
            'journal_entry': {},
            'meals_entry': None,
        }

    state = user_data[user.id]['state']

    if state == STATE_WRITING_SITUATION:
        user_data[user.id]['journal_entry']['situation'] = text
        user_data[user.id]['state'] = STATE_WRITING_THOUGHTS
        await update.message.reply_text("Какие мысли у вас возникли в этой ситуации?")

    elif state == STATE_WRITING_THOUGHTS:
        user_data[user.id]['journal_entry']['thoughts'] = text
        user_data[user.id]['state'] = STATE_WRITING_EMOTIONS
        await update.message.reply_text("Какие эмоции вы испытывали?")

    elif state == STATE_WRITING_EMOTIONS:
        user_data[user.id]['journal_entry']['emotions'] = text
        user_data[user.id]['state'] = STATE_WRITING_SENSATIONS
        await update.message.reply_text("Какие физические ощущения вы заметили?")

    elif state == STATE_WRITING_SENSATIONS:
        user_data[user.id]['journal_entry']['sensations'] = text
        user_data[user.id]['state'] = STATE_WRITING_ACTIONS
        await update.message.reply_text("Что вы сделали в этой ситуации?")

    elif state == STATE_WRITING_ACTIONS:
        user_data[user.id]['journal_entry']['actions'] = text
        user_data[user.id]['state'] = STATE_WRITING_DESIRES
        await update.message.reply_text("Что вы хотели сделать в этой ситуации?")

    elif state == STATE_WRITING_DESIRES:
        user_data[user.id]['journal_entry']['desires'] = text
        user_data[user.id]['state'] = STATE_NONE
        await update.message.reply_text(
            "Запись добавлена в дневник!",
            reply_markup=get_main_keyboard()
        )

    elif state == STATE_WRITING_MEALS:
        if text.isdigit():
            user_data[user.id]['meals_entry'] = int(text)
            user_data[user.id]['state'] = STATE_NONE
            await update.message.reply_text(
                f"Записано {text} приёмов пищи.",
                reply_markup=get_main_keyboard()
            )
        else:
            await update.message.reply_text("Пожалуйста, введите число.")


async def send_daily_report(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Формирует и отправляет отчёт за день"""
    if user_id not in user_data:
        return

    report = "📊 Отчёт за день\n\n"

    if user_data[user_id]['journal_entry']:
        report += "📝 Дневник:\n"
        for key, value in user_data[user_id]['journal_entry'].items():
            report += f"• {key.capitalize()}: {value}\n"
        report += "\n"
    else:
        report += "📝 Дневник: нет записей\n\n"

    if user_data[user_id]['meals_entry'] is not None:
        report += f"🍎 Питание: {user_data[user_id]['meals_entry']} приёмов пищи\n"
    else:
        report += "🍎 Питание: нет данных\n"

    await context.bot.send_message(
        chat_id=user_id,
        text=report,
        reply_markup=get_main_keyboard()
    )


async def morning_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Утреннее напоминание"""
    for user_id in user_data:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="Доброе утро! Не забудьте записать свои мысли и переживания в дневник.",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке утреннего напоминания пользователю {user_id}: {e}")


async def evening_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Вечернее напоминание"""
    for user_id in user_data:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="Добрый вечер! Не забудьте записать приёмы пищи за сегодня.",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке вечернего напоминания пользователю {user_id}: {e}")


def main() -> None:
    """Запуск бота"""
    # Создаем Application с токеном вашего бота
    application = (
        Application.builder()
        .token("7200943849:AAEAKQlY8wt9yFh_KX4Z1CAkOUznOD8RarU")
        .build()
    )

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Напоминания (только если JobQueue доступен)
    if hasattr(application, 'job_queue') and application.job_queue:
        application.job_queue.run_daily(morning_reminder, time=time(hour=9, minute=0), days=tuple(range(7)))
        application.job_queue.run_daily(evening_reminder, time=time(hour=21, minute=0), days=tuple(range(7)))
    else:
        logger.warning("JobQueue не доступен. Напоминания не будут работать.")

    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    main()