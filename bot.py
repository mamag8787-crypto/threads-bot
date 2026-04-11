import os
import anthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

print(f"TOKEN starts with: {str(TELEGRAM_TOKEN)[:10] if TELEGRAM_TOKEN else 'EMPTY'}")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def agent_analyst(transcript: str) -> str:
    prompt = (
        "Ты аналитик контента. Извлеки из транскрипта вебинара ровно 10 самых ценных идей.\n\n"
        "Требования:\n"
        "- Каждая идея самостоятельная и законченная\n"
        "- Формулируй чётко и конкретно, без воды\n"
        "- Сохраняй экспертный тон автора\n"
        "- Нумерованный список: 1. ... 2. ... и т.д.\n\n"
        "ТРАНСКРИПТ:\n"
        + transcript +
        "\n\nВыдай только список из 10 идей."
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def agent_structurer(ideas: str) -> str:
    prompt = (
        "Ты стратег контента для Threads. Распредели 10 идей по структуре ветки.\n\n"
        "Структура:\n"
        "- Пост 1: ХУК через личную боль или потерю\n"
        "- Посты 2-3: ПРОБЛЕМА — читатель узнаёт себя\n"
        "- Посты 4-7: ТРАНСФОРМАЦИЯ — показывай было/стало с конкретикой\n"
        "- Посты 8-9: ДОКАЗАТЕЛЬСТВО — личный кейс с цифрами\n"
        "- Пост 10: CTA через срочность или страх упустить\n\n"
        "Для каждого поста: [Пост N] Роль: ... | Идея: ... | Ключевое сообщение: ...\n\n"
        "ИДЕИ:\n"
        + ideas +
        "\n\nВыдай только структуру."
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def agent_writer(structure: str, ideas: str) -> str:
    prompt = (
        "Ты копирайтер для Threads. Напиши ветку из 10 постов на русском языке.\n\n"
        "СТИЛЬ:\n"
        "- Экспертный, уверенный, без воды\n"
        "- Длина каждого поста: 300-500 символов\n"
        "- Никаких хэштегов, максимум 2 эмодзи на пост\n\n"
        "ПРАВИЛА ВИРУСНОСТИ:\n"
        "- Пост 1: хук через личную боль или потерю\n"
        "- В каждом посте должно быть напряжение\n"
        "- Посты 4-7: показывай трансформацию было/стало с конкретными деталями\n"
        "- Один пост должен содержать личный кейс с реальной цифрой\n"
        "- Избегай: мало кто знает, скрытая настройка, секрет\n"
        "- Пост 10: CTA через страх упустить или срочность\n"
        "- Читатель должен узнавать себя в каждом посте\n\n"
        "СТРУКТУРА:\n"
        + structure +
        "\n\nИДЕИ:\n"
        + ideas +
        "\n\nФормат:\n"
        "━━━ ПОСТ 1 ━━━\n"
        "[текст]\n\n"
        "━━━ ПОСТ 2 ━━━\n"
        "[текст]\n\n"
        "...до поста 10."
    )
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def agent_reviewer(posts: str) -> str:
    prompt = (
        "Ты редактор вирусного контента для Threads. Проверь ветку из 10 постов.\n\n"
        "Проверь каждый пост:\n"
        "- Длина не превышает 500 символов\n"
        "- Пост 1 начинается с личной боли или потери\n"
        "- Есть напряжение и ощущение что читатель упускает что-то важное\n"
        "- Посты 4-7 показывают трансформацию, не просто описывают\n"
        "- Есть хотя бы один пост с конкретной цифрой или личным кейсом\n"
        "- Нет заезженных фраз: мало кто знает, скрытая настройка, секрет\n"
        "- Пост 10 создаёт срочность или страх упустить\n"
        "- Читатель узнаёт себя в тексте\n"
        "- Нет воды и повторов\n\n"
        "ВАЖНО: выдай ТОЛЬКО финальные посты с разделителями ━━━ ПОСТ N ━━━\n"
        "Без комментариев, без списка исправлений, без заголовков.\n\n"
        "ВЕТКА:\n"
        + posts
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    transcript = update.message.text

    if len(transcript) < 100:
        await update.message.reply_text("Пришли транскрипт вебинара. Минимум 100 символов.")
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

        parts = final_posts.split("━━━ ПОСТ ")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            lines = part.split("━━━", 1)
            if len(lines) == 2:
                number = lines[0].strip()
                text = lines[1].strip()
                await update.message.reply_text("📌 ПОСТ " + number + "\n\n" + text)
            else:
                await update.message.reply_text(part)

        await update.message.reply_text("Копируй и публикуй в Threads!")

    except Exception as e:
        await update.message.reply_text("Ошибка: " + str(e))


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
