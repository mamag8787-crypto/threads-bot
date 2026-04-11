import os
import time
import anthropic
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
THREADS_TOKEN = os.getenv("THREADS_TOKEN")

print(f"TOKEN starts with: {str(TELEGRAM_TOKEN)[:10] if TELEGRAM_TOKEN else 'EMPTY'}")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

pending_posts = {}


def get_threads_user_id() -> str:
    url = "https://graph.threads.net/v1.0/me"
    params = {"fields": "id,username", "access_token": THREADS_TOKEN}
    response = httpx.get(url, params=params, timeout=30.0)
    return response.json().get("id")


def create_container(user_id: str, text: str, reply_to_id: str = None) -> str:
    url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_TOKEN
    }
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    response = httpx.post(url, params=params, timeout=30.0)
    return response.json().get("id")


def publish_container(user_id: str, creation_id: str) -> str:
    url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
    params = {
        "creation_id": creation_id,
        "access_token": THREADS_TOKEN
    }
    response = httpx.post(url, params=params, timeout=30.0)
    return response.json().get("id")


def publish_thread(posts: list) -> dict:
    user_id = get_threads_user_id()
    if not user_id:
        return {"error": "Не удалось получить user_id"}

    published_ids = []

    for i, text in enumerate(posts):
        try:
            # Создаём контейнер
            reply_to = published_ids[-1] if published_ids else None
            creation_id = create_container(user_id, text, reply_to_id=reply_to)

            if not creation_id:
                return {"error": f"Не удалось создать контейнер для поста {i+1}"}

            # Небольшая пауза перед публикацией
            time.sleep(1)

            # Публикуем
            post_id = publish_container(user_id, creation_id)

            if not post_id:
                return {"error": f"Не удалось опубликовать пост {i+1}"}

            published_ids.append(post_id)

            # Пауза между постами чтобы не получить rate limit
            if i < len(posts) - 1:
                time.sleep(2)

        except Exception as e:
            return {"error": f"Ошибка на посте {i+1}: " + str(e)}

    return {"success": True, "published": len(published_ids)}


def agent_analyst(transcript: str) -> str:
    prompt = (
        "Ты аналитик контента. Извлеки из транскрипта вебинара ровно 10 самых ценных идей.\n\n"
        "Требования:\n"
        "- Каждая идея самостоятельная и законченная\n"
        "- Формулируй чётко и конкретно, без воды\n"
        "- Сохраняй экспертный тон автора\n"
        "- Нумерованный список: 1. ... 2. ... и т.д.\n\n"
        "ТРАНСКРИПТ:\n" + transcript +
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
        "ИДЕИ:\n" + ideas +
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
        "- Читатель должен узнавать себя в каждом посте\n"
        "- ВАЖНО: пиши ТОЛЬКО на русском языке, даже если транскрипт на другом языке\n\n"
        "СТРУКТУРА:\n" + structure +
        "\n\nИДЕИ:\n" + ideas +
        "\n\nФормат:\n"
        "━━━ ПОСТ 1 ━━━\n[текст]\n\n"
        "━━━ ПОСТ 2 ━━━\n[текст]\n\n"
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
        "- Нет воды и повторов\n"
        "- Все посты на русском языке\n\n"
        "ВАЖНО: выдай ТОЛЬКО финальные посты с разделителями ━━━ ПОСТ N ━━━\n"
        "Без комментариев, без списка исправлений, без заголовков.\n\n"
        "ВЕТКА:\n" + posts
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def parse_posts(final_posts: str) -> list:
    post_texts = []
    parts = final_posts.split("━━━ ПОСТ ")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.split("━━━", 1)
        if len(lines) == 2:
            text = lines[1].strip()
        else:
            text = part.strip()
        if text:
            post_texts.append(text)
    return post_texts


async def process_transcript(update: Update, transcript: str):
    if len(transcript) < 100:
        await update.message.reply_text("Транскрипт слишком короткий. Минимум 100 символов.")
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

        post_texts = parse_posts(final_posts)

        user_id = update.message.from_user.id
        pending_posts[user_id] = post_texts

        await update.message.reply_text("Готово! Вот твоя ветка:")

        # Отправляем все посты чистым текстом
        for text in post_texts:
            await update.message.reply_text(text)

        # Одна кнопка публикации всей ветки
        keyboard = [[InlineKeyboardButton(
            "🚀 Опубликовать всю ветку в Threads",
            callback_data="publish_thread_" + str(user_id)
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Нажми кнопку чтобы опубликовать все 10 постов цепочкой в Threads.",
            reply_markup=reply_markup
        )

    except Exception as e:
        await update.message.reply_text("Ошибка: " + str(e))


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("publish_thread_"):
        return

    user_id = int(data.split("publish_thread_")[1])
    posts = pending_posts.get(user_id, [])

    if not posts:
        await query.message.reply_text("Посты не найдены. Сгенерируй ветку заново.")
        return

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("Публикую ветку в Threads... (~30 секунд)")

    try:
        result = publish_thread(posts)
        if "error" in result:
            await query.message.reply_text("Ошибка публикации: " + str(result["error"]))
        else:
            count = result.get("published", 0)
            await query.message.reply_text(
                "Ветка опубликована в Threads!\n"
                "Опубликовано постов: " + str(count)
            )
    except Exception as e:
        await query.message.reply_text("Ошибка: " + str(e))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_transcript(update, update.message.text)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    mime = doc.mime_type or ""
    name = doc.file_name or ""

    if not (mime == "text/plain" or name.endswith(".txt") or name.endswith(".docx")):
        await update.message.reply_text("Поддерживаю файлы .txt и .docx\nИли просто вставь текст сообщением.")
        return

    await update.message.reply_text("Читаю файл...")

    file = await context.bot.get_file(doc.file_id)
    file_bytes = await file.download_as_bytearray()

    if name.endswith(".docx"):
        try:
            import docx
            import io
            document = docx.Document(io.BytesIO(bytes(file_bytes)))
            transcript = "\n".join([para.text for para in document.paragraphs if para.text.strip()])
        except Exception as e:
            await update.message.reply_text("Ошибка чтения .docx: " + str(e))
            return
    else:
        try:
            transcript = file_bytes.decode("utf-8")
        except Exception:
            try:
                transcript = file_bytes.decode("cp1251")
            except Exception as e:
                await update.message.reply_text("Ошибка чтения файла: " + str(e))
                return

    await process_transcript(update, transcript)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я создаю ветки для Threads из твоих транскриптов.\n\n"
        "Как использовать:\n"
        "1. Пришли транскрипт — текстом или файлом (.txt / .docx)\n"
        "2. Подожди ~60 секунд\n"
        "3. Просмотри 10 постов\n"
        "4. Нажми одну кнопку — вся ветка улетит в Threads цепочкой\n\n"
        "Транскрипт может быть на любом языке — посты всегда на русском."
    )


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
