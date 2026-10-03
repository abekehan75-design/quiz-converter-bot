#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот для конвертации вопросов из формата документа в формат приложения Ассистент
Принимает: .docx файл или текст
Спрашивает номер правильного варианта один раз для всех вопросов
Возвращает: .txt файл с конвертированными вопросами
"""

import re
import os
from io import BytesIO
from docx import Document
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Токен бота берётся из переменной окружения для безопасности
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8911964732:AAHlFZ2Ads45apMnIyrSdS1pMhZK7OHI4eA")

# Состояния для ConversationHandler
SELECTING_ANSWER = 1


def parse_questions(text: str) -> list:
    """
    Парсит текст и извлекает вопросы и варианты ответов
    """
    questions = []
    lines = text.strip().split('\n')

    current_question = None
    variants = []

    for line in lines:
        line = line.strip()

        if not line:
            if current_question and variants:
                questions.append({
                    'question': current_question,
                    'variants': variants
                })
                current_question = None
                variants = []
            continue

        if '<question>' in line:
            if current_question and variants:
                questions.append({
                    'question': current_question,
                    'variants': variants
                })
                variants = []

            question_text = re.sub(r'</?question>', '', line).strip()
            current_question = question_text

        elif '<variant>' in line:
            variant_text = re.sub(r'</?variant>', '', line).strip()
            if variant_text:
                variants.append(variant_text)

    if current_question and variants:
        questions.append({
            'question': current_question,
            'variants': variants
        })

    return questions


def generate_output(questions: list, correct_index: int) -> str:
    """
    Генерирует финальный текст в формате ?/+/-
    correct_index - номер правильного варианта (0-based)
    """
    result = []

    for q in questions:
        result.append(f"?{q['question']}")

        for i, variant in enumerate(q['variants']):
            if i == correct_index:
                result.append(f"+{variant}")
            else:
                result.append(f"-{variant}")

        result.append("")  # Пустая строка между вопросами

    return '\n'.join(result)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    welcome_message = (
        "👋 Привет! Я бот для конвертации вопросов.\n\n"
        "📄 Отправь мне:\n"
        "• Документ .docx с вопросами\n"
        "• Или текст напрямую в сообщении\n\n"
        "📝 Формат входных данных:\n"
        "<question>Вопрос?\n"
        "<variant>Вариант 1\n"
        "<variant>Вариант 2\n"
        "<variant>Вариант 3\n\n"
        "Я спрошу, какой номер варианта правильный для ВСЕХ вопросов!\n\n"
        "📥 Результат будет в формате:\n"
        "?Вопрос?\n"
        "+Правильный вариант\n"
        "-Неправильный вариант\n"
        "-Неправильный вариант"
    )
    await update.message.reply_text(welcome_message)
    return ConversationHandler.END


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка .docx документов"""
    document = update.message.document

    if not document.file_name.endswith('.docx'):
        await update.message.reply_text(
            "❌ Пожалуйста, отправь файл в формате .docx"
        )
        return ConversationHandler.END

    try:
        processing_msg = await update.message.reply_text("⏳ Обрабатываю документ...")

        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()

        doc = Document(BytesIO(file_bytes))
        full_text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                full_text.append(paragraph.text.strip())

        original_text = '\n'.join(full_text)
        questions = parse_questions(original_text)

        await processing_msg.delete()

        if not questions:
            await update.message.reply_text(
                "❌ Не удалось найти вопросы в документе.\n"
                "Убедись, что формат правильный:\n"
                "<question>Текст вопроса\n"
                "<variant>Вариант 1\n"
                "<variant>Вариант 2"
            )
            return ConversationHandler.END

        context.user_data['questions'] = questions
        context.user_data['original_filename'] = document.file_name

        return await ask_correct_variant(update, context)

    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка при обработке документа:\n{str(e)}"
        )
        return ConversationHandler.END


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_text = update.message.text

    try:
        questions = parse_questions(user_text)

        if not questions:
            await update.message.reply_text(
                "❌ Не удалось распознать формат.\n"
                "Убедись, что используешь правильный формат:\n\n"
                "<question>Текст вопроса\n"
                "<variant>Вариант 1\n"
                "<variant>Вариант 2"
            )
            return ConversationHandler.END

        context.user_data['questions'] = questions
        context.user_data['original_filename'] = None

        return await ask_correct_variant(update, context)

    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка: {str(e)}"
        )
        return ConversationHandler.END


async def ask_correct_variant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Спрашивает пользователя, какой номер варианта правильный для ВСЕХ вопросов"""
    questions = context.user_data['questions']

    # Находим максимальное количество вариантов
    max_variants = max(len(q['variants']) for q in questions)

    message_text = (
        f"📊 Найдено вопросов: {len(questions)}\n\n"
        "❓ Какой номер варианта правильный для ВСЕХ вопросов?\n\n"
        "Например:\n"
        "• Если правильный ответ всегда первый вариант → нажми 1\n"
        "• Если правильный ответ всегда второй вариант → нажми 2\n"
        "• И так далее..."
    )

    keyboard = []
    for i in range(max_variants):
        keyboard.append([
            InlineKeyboardButton(
                f"{i + 1}",
                callback_data=f"correct_{i}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text=message_text,
        reply_markup=reply_markup
    )

    return SELECTING_ANSWER


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия на кнопку с номером правильного варианта"""
    query = update.callback_query
    await query.answer()

    correct_index = int(query.data.split('_')[1])

    questions = context.user_data['questions']
    output_text = generate_output(questions, correct_index)

    filename = context.user_data.get('original_filename')
    if filename:
        output_filename = filename.replace('.docx', '_converted.txt')
    else:
        output_filename = 'converted_questions.txt'

    output_file = BytesIO(output_text.encode('utf-8'))
    output_file.name = output_filename

    await query.edit_message_text(
        f"✅ Отлично! Вариант {correct_index + 1} выбран как правильный для всех вопросов.\n"
        "Отправляю результат..."
    )

    await query.message.reply_document(
        document=output_file,
        filename=output_filename,
        caption=f"✅ Конвертация завершена!\n📊 Вопросов: {len(questions)}\n✓ Правильный вариант: {correct_index + 1}"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена процесса конвертации"""
    await update.message.reply_text(
        "❌ Конвертация отменена.\n"
        "Отправь новый документ или текст, чтобы начать заново."
    )
    context.user_data.clear()
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "📖 Инструкция:\n\n"
        "1️⃣ Подготовь .docx документ или текст с вопросами\n"
        "2️⃣ Отправь его мне в чат\n"
        "3️⃣ Выбери номер варианта, который правильный для ВСЕХ вопросов (1, 2, 3...)\n"
        "4️⃣ Получи .txt файл с конвертированными вопросами\n\n"
        "📝 Формат входных данных:\n"
        "<question>Столица России?\n"
        "<variant>Москва\n"
        "<variant>Санкт-Петербург\n"
        "<variant>Казань\n\n"
        "📤 Формат выходного файла:\n"
        "?Столица России?\n"
        "+Москва\n"
        "-Санкт-Петербург\n"
        "-Казань\n\n"
        "Команды:\n"
        "/start - Начать работу\n"
        "/help - Эта справка\n"
        "/cancel - Отменить текущую конвертацию"
    )
    await update.message.reply_text(help_text)


def main():
    """Запуск бота"""
    if not TELEGRAM_TOKEN:
        print("❌ ОШИБКА: Установи переменную окружения TELEGRAM_TOKEN")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # ConversationHandler для управления процессом выбора ответа
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Document.FileExtension("docx"), handle_document),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
        ],
        states={
            SELECTING_ANSWER: [
                CallbackQueryHandler(button_callback, pattern="^correct_")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
        per_user=True,
        per_chat=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)

    print("🤖 Бот запущен и готов к работе!")
    print("📄 Принимает: .docx файлы и текст")
    print("❓ Спрашивает номер правильного варианта один раз для всех вопросов")
    print("📤 Возвращает: .txt файлы")

    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
