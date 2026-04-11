import os
from dotenv import load_dotenv
import anthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

load_dotenv()

load_dotenv()

TELEGRAM_TOKEN = "8626710924:AAEoGe-JoTIkYGKB24zlXrDhUV5QJ5D_Hbs"


print(f"TOKEN starts with: {str(TELEGRAM_TOKEN)[:10] if TELEGRAM_TOKEN else 'EMPTY'}")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def agent_analyst(transcript: str) -> str:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""Ты аналитик контента. Извлеки из транскрипта вебинара ровно 10 самых ценных идей.

Требования:
- Каждая идея самостоятельная и законченная
- Формулируй чётко и конкретно, без воды
- Сохраняй экспертный тон автора
- Нумерованный список: 1. ... 2. ... и т.д.

ТРАНСКРИПТ:
{transcript}

Выдай только список из 10 идей."""
        }]
    )
    return response.content[0].text


def agent_structurer(ideas: str) -> str:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""Ты стратег контента для Threads. Распредели 10 идей по структуре ветки.

Структура:
- Пост 1: ХВАТАЮЩИЙ ХУК
- Посты 2-9: РАЗВИТИЕ каждой идеи
- Пост 10: ЗАВЕРШЕНИЕ + призыв к действию

Для каждого поста: [Пост N] Роль: ... | Идея: ... | Ключевое сообщение: ...

ИДЕИ:
{ideas}

Выдай только структуру."""
        }]
    )
    return response.content[0].text


def agent_writer(structure: str, ideas: str) -> str:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": f"""Ты копирайтер для Threads. Напиши ветку из 10 постов на русском языке.

СТИЛЬ:
- Экспертный и структурированный
- Конкретные факты, чёткие тезисы, без воды
- Длина каждого поста: 300-500 символов
- Никаких хэштегов
- Максимум 2 эмодзи на пост

СТРУКТУРА:
{structure}

ИДЕИ:
{ideas}

Формат:
━━━ ПОСТ 1 ━━━
[текст]

━━━ ПОСТ 2 ━━━
[текст]

...до поста 10."""
        }]
    )
    return response.content[0].text


def agent_reviewer(posts: str) -> str:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": f"""Ты редактор. Проверь ветку из 10 постов для Threads.

Проверь:
- Длина не превышает 500 символов
- Хук в первом посте цепляет
- Последний пост содержит призыв к действию
- Тон везде экспертный и уверенный
- Нет воды и повторов

ВЕТКА:
{posts}

Выдай финальную версию с разделителями ━━━ ПОСТ N ━━━"""
        }]
    )
    return response.content[0].text


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    transcript = update.message.text

    if len(transcript) < 100:
        await update.message.reply_text(
            "Пришли транскрипт вебинара. Минимум 100 символов."
        )
        return

    await update.message.reply_text("Агент 1: анализирую транскрипт...")

    try:
        ideas = agent_analyst(transcript)
        await update.message.reply_text("Агент 2: строю структуру ветки...")

        structure = agent_structurer(ideas)
        await update.message.reply_text("Агент 3: пишу посты...")

        raw_posts = agent_writer(structure, ideas)
        await update.message.reply_text("Агент 4: финальная проверка...")

        final_posts = agent_reviewer(raw_posts)
        await update.message.reply_text("Готово! Вот твоя ветка для Threads:")

        if len(final_posts) > 4000:
            parts = [final_posts[i:i+4000] for i in range(0, len(final_posts), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(final_posts)

        await update.message.reply_text("Копируй и публикуй в Threads!")

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я создаю ветки для Threads из твоих транскриптов.\n\n"
        "Как использовать:\n"
        "1. Скопируй транскрипт вебинара\n"
        "2. Вставь сюда и отправь\n"
        "3. Получи готовую ветку из 10 постов\n\n"
        "Обработка занимает около 60 секунд."
    )


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
