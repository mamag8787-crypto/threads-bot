import os
from dotenv import load_dotenv
import anthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from telegram.request import HTTPXRequest

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

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
- Пост 1: ХВАТАЮЩИЙ ХУК — провокационный вопрос или неожиданное утверждение
- Посты 2-9: РАЗВИТИЕ — каждая идея как отдельный тезис
- Пост 10: ЗАВЕРШЕНИЕ — главный вывод + призыв к действию

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

Формат вывода:
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
            "content": f"""Ты редактор. Проверь ветку из 10 постов для Threads и исправь если нужно.

Проверь:
- Длина не превышает 500 символов
- Хук в первом посте цепляет
- Каждый пост тянет читать следующий
- Последний пост содержит призыв к действию
- Тон везде экспертный и уверенный
- Нет воды и повторов

ВЕТКА:
{posts}

Выдай финальную версию всех 10 постов с разделителями ━━━ ПОСТ N ━━━"""
        }]
    )
    return response.content[0].text


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    transcript = update.message.text

    if len(transcript) < 100:
        await update.message.reply_text(
            "Пришли транскрипт вебинара или обучающего материала.\n"
            "Минимум ~100 символов для обработки."
        )
        return

    await update.message.reply_text("Запускаю агентов...\n\nАгент 1: анализирую транскрипт")

    try:
        ideas = agent_analyst(transcript)
        await update.message.reply_text("Агент 1 готов — извлёк 10 идей\n\nАгент 2: строю структуру ветки")

        structure = agent_structurer(ideas)
        await update.message.reply_text("Агент 2 готов — структура готова\n\nАгент 3: пишу посты")

        raw_posts = agent_writer(structure, ideas)
        await update.message.reply_text("Агент 3 готов — 10 постов написаны\n\nАгент 4: финальная проверка")

        final_posts = agent_reviewer(raw_posts)
        await update.message.reply_text("Все агенты завершили работу!\n\nВот твоя ветка для Threads:")

        if len(final_posts) > 4000:
            parts = [final_posts[i:i+4000] for i in range(0, len(final_posts), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(final_posts)

        await update.message.reply_text("Готово! Копируй и публикуй в Threads.")

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}\n\nПопробуй ещё раз.")


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
    proxies = [
        "socks5://91.108.4.1:1080",
        "socks5://91.108.56.1:1080",
        "socks5://149.154.175.1:1080",
    ]

    app = None
    for proxy in proxies:
        try:
            request = HTTPXRequest(proxy=proxy)
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).request(request).build()
            print(f"Бот запущен через прокси: {proxy}")
            break
        except Exception:
            print(f"Прокси не работает: {proxy}")
            continue

    if app is None:
        print("Все прокси недоступны. Попробуй включить VPN.")
        return

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
