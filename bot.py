#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот для конвертации вопросов из формата документа в формат приложения Ассистент
Принимает: .docx файл
Возвращает: .txt файл с конвертированными вопросами
"""

import re
import os
from io import BytesIO
from docx import Document
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Вставь сюда токен от BotFather
TELEGRAM_TOKEN = "8911964732:AAHlFZ2Ads45apMnIyrSdS1pMhZK7OHI4eA"


def convert_quiz_format(text: str) -> str:
    """
    Конвертирует формат вопросов из <question>/<variant> в ?/+/- формат

    Входной формат:
    <question>Вопрос текст
    <variant>Вариант 1
    <variant>Вариант 2
    <variant>Вариант 3

    Выходной формат:
    ?Вопрос текст
    +Вариант 1 (первый - всегда правильный)
    -Вариант 2
    -Вариант 3
    """
    result = []
    lines = text.strip().split('\n')

    current_question = None
    variants = []

    for line in lines:
        line = line.strip()

        if not line:
            # Если пустая строка и есть накопленный вопрос, сохраняем его
            if current_question and variants:
                result.append(f"?{current_question}")
                result.append(f"+{variants[0]}")  # Первый вариант - правильный
                for variant in variants[1:]:
                    result.append(f"-{variant}")
                result.append("")  # Пустая строка между вопросами

                current_question = None
                variants = []
            continue

        # Проверяем, есть ли теги
        if '<question>' in line:
            # Сохраняем предыдущий вопрос, если был
            if current_question and variants:
                result.append(f"?{current_question}")
                result.append(f"+{variants[0]}")
                for variant in variants[1:]:
                    result.append(f"-{variant}")
                result.append("")
                variants = []

            # Извлекаем текст вопроса
            question_text = re.sub(r'</?question>', '', line).strip()
            current_question = question_text

        elif '<variant>' in line:
            # Извлекаем текст варианта
            variant_text = re.sub(r'</?variant>', '', line).strip()
            if variant_text:
                variants.append(variant_text)

    # Добавляем последний вопрос, если он есть
    if current_question and variants:
        result.append(f"?{current_question}")
        result.append(f"+{variants[0]}")
        for variant in variants[1:]:
            result.append(f"-{variant}")

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
        "📥 Я конвертирую в формат:\n"
        "?Вопрос?\n"
        "+Вариант 1 (правильный)\n"
        "-Вариант 2\n"
        "-Вариант 3\n\n"
        "⚠️ Первый вариант автоматически помечается как правильный!"
    )
    await update.message.reply_text(welcome_message)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка документов"""
    document = update.message.document

    # Проверяем, что это .docx файл
    if not document.file_name.endswith('.docx'):
        await update.message.reply_text(
            "❌ Пожалуйста, отправь файл в формате .docx"
        )
        return

    try:
        # Отправляем уведомление о начале обработки
        processing_msg = await update.message.reply_text("⏳ Обрабатываю документ...")

        # Скачиваем файл
        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()

        # Читаем .docx документ
        doc = Document(BytesIO(file_bytes))

        # Извлекаем весь текст из документа
        full_text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                full_text.append(paragraph.text.strip())

        original_text = '\n'.join(full_text)

        # Конвертируем формат
        converted_text = convert_quiz_format(original_text)

        if not converted_text:
            await processing_msg.edit_text(
                "❌ Не удалось найти вопросы в документе.\n"
                "Убедись, что формат правильный:\n"
                "<question>Текст вопроса\n"
                "<variant>Вариант 1\n"
                "<variant>Вариант 2"
            )
            return

        # Создаём имя выходного файла
        output_filename = document.file_name.replace('.docx', '_converted.txt')

        # Отправляем результат как файл
        output_file = BytesIO(converted_text.encode('utf-8'))
        output_file.name = output_filename

        await update.message.reply_document(
            document=output_file,
            filename=output_filename,
            caption=f"✅ Конвертировано успешно!\n📊 Найдено вопросов: {converted_text.count('?')}"
        )

        # Удаляем сообщение о процессе
        await processing_msg.delete()

    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка при обработке документа:\n{str(e)}\n\n"
            "Проверь формат документа и попробуй снова."
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_text = update.message.text

    try:
        # Конвертируем формат
        converted = convert_quiz_format(user_text)

        if not converted:
            await update.message.reply_text(
                "❌ Не удалось распознать формат.\n"
                "Убедись, что используешь правильный формат:\n\n"
                "<question>Текст вопроса\n"
                "<variant>Вариант 1\n"
                "<variant>Вариант 2"
            )
            return

        # Если результат большой (больше 1000 символов), отправляем файлом
        if len(converted) > 1000:
            output_file = BytesIO(converted.encode('utf-8'))
            output_file.name = 'converted_questions.txt'

            await update.message.reply_document(
                document=output_file,
                filename='converted_questions.txt',
                caption=f"✅ Конвертировано успешно!\n📊 Найдено вопросов: {converted.count('?')}"
            )
        else:
            # Если результат короткий, отправляем текстом
            await update.message.reply_text(
                f"✅ Результат конвертации:\n\n{converted}",
                parse_mode=None
            )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка: {str(e)}"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "📖 Инструкция:\n\n"
        "1️⃣ Подготовь .docx документ с вопросами\n"
        "2️⃣ Отправь документ в этот чат\n"
        "3️⃣ Получи .txt файл с конвертированными вопросами\n\n"
        "📝 Формат входного документа:\n"
        "<question>Столица России?\n"
        "<variant>Москва\n"
        "<variant>Санкт-Петербург\n"
        "<variant>Казань\n\n"
        "<question>Следующий вопрос?\n"
        "<variant>Ответ 1\n"
        "<variant>Ответ 2\n\n"
        "📤 Формат выходного файла:\n"
        "?Столица России?\n"
        "+Москва\n"
        "-Санкт-Петербург\n"
        "-Казань\n\n"
        "?Следующий вопрос?\n"
        "+Ответ 1\n"
        "-Ответ 2\n\n"
        "⚠️ Первый вариант всегда правильный (+)"
    )
    await update.message.reply_text(help_text)


def main():
    """Запуск бота"""
    # Проверка токена
    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ОШИБКА: Установи токен бота в переменной TELEGRAM_TOKEN")
        print("📝 Получить токен можно у @BotFather в Telegram")
        return

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.FileExtension("docx"), handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Запускаем бота
    print("🤖 Бот запущен и готов к работе!")
    print("📄 Принимает: .docx файлы")
    print("📤 Возвращает: .txt файлы")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
