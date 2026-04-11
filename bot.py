import os
from dotenv import load_dotenv
import anthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

print(f"TOKEN starts with: {str(TELEGRAM_TOKEN)[:10] if TELEGRAM_TOKEN else 'EMPTY'}")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def agent_analyst(transcript: str) -> str:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
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
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""Ты стратег контента для Threads. Распредели 10 идей по структуре ветки.

Структура:
- Пост 1: ХУК через личную боль или потерю
- Посты 2-3: ПРОБЛЕМА — читатель узнаёт себя
- Посты 4-7: ТРАНСФОРМАЦИЯ — показывай было/стало с конкретикой
- Пост 8-9: ДОКАЗАТЕЛЬСТВО — личный кейс с цифрами
- Пост 10: CTA через срочность или страх упустить

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
- Экспертный, уверенный, без воды
- Длина каждого поста: 300-500 символов
- Никаких хэштегов, максимум 2 эмодзи на пост

ПРАВИЛА ВИРУСНОСТИ:
- Пост 1: хук через личную боль или потерю ("я потерял X пока не узнал", "3 месяца делал неправильно")
- В каждом посте должно быть напряжение — читатель должен чувствовать что упускает что-то важное
- Посты 4-7: не объясняй абстрактно — показывай трансформацию "было/стало" с конкретными деталями
- Один пост должен содержать личный кейс с реальной цифрой или результатом
- Избегай заезженных приёмов: "скрытая настройка", "мало кто знает", "секрет"
- Пост 10: CTA через страх упустить или срочность — не просто "переходи по ссылке", а причина действовать сейчас
- Читатель должен узнавать себя в каждом посте

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
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": f"""Ты редактор вирусного контента для Threads. Проверь ветку из 10 постов.

Проверь каждый пост:
- Длина не превышает 500 символов
- Пост 1 начинается с личной боли или потери — не с абстракции
- Есть напряжение и ощущение что читатель упускает что-то важное
- Посты 4-7 показывают трансформацию, не просто описывают
- Есть хотя бы один пост с конкретной цифрой или личным кейсом
- Нет заезженных фраз: "мало кто знает", "скрытая настройка", "секрет"
- Пост 10 создаёт срочность или страх упустить
- Читатель узнаёт себя в тексте
- Нет воды и повторов

Если что-то не так — исправь прямо в тексте.

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
        await update.message.reply_text("Готово! Вот твоя ветка для Threads 👇")

        # Отправляем каждый пост отдельным сообщением
        parts = final_posts.split("━━━ ПОСТ ")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Извлекаем номер и текст
            lines = part.split("━━━", 1)
            if len(lines) == 2:
                number = lines[0].strip()
                text = lines[1].strip()
                await update.message.reply_text(f"📌 ПОСТ {number}\n\n{text}")
            else:
                await update.message.reply_text(part)

        await update.message.reply_text("✅ Все посты готовы. Копируй и публикуй в Threads!")

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я создаю ветки для Threads из твоих транскриптов.\n\n"
        "Как использовать:\n"
        "1. Скопируй транскрипт вебинара\n"
        "2. Вставь сюда и отправь\n"
        "3. Получи готовую ветку из 10 постов — каждый отдельным сообщением\n\n"
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
