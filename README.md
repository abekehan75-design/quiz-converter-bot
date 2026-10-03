# Quiz Converter Telegram Bot

Telegram бот для конвертации вопросов из формата документа в формат приложения "Ассистент".

## Формат входных данных (.docx)

```
<question>Вопрос текст
<variant>Вариант 1
<variant>Вариант 2
<variant>Вариант 3
```

## Формат выходных данных (.txt)

```
?Вопрос текст
+Вариант 1
-Вариант 2
-Вариант 3
```

⚠️ Первый вариант автоматически помечается как правильный ответ.

## Деплой на Render.com

1. Создай новый Web Service на [Render.com](https://render.com)
2. Подключи этот GitHub репозиторий
3. Настройки:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Environment Variables**: добавь `TELEGRAM_TOKEN` с токеном от BotFather

## Локальный запуск

```bash
export TELEGRAM_TOKEN="your_token_here"
python bot.py
```

## Команды бота

- `/start` - Приветствие и инструкции
- `/help` - Подробная справка

Отправь боту .docx файл для конвертации.
