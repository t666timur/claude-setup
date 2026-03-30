"""
Claude Bot v2 — использует Anthropic API напрямую (без subprocess)
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# ── Конфиг ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY")
ALLOWED_USERS   = [int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip()]
HISTORY_FILE    = Path("/home/timur/claude_logs/shared_history.json")
PHOTOS_DIR      = Path("/home/timur/claude_logs/photos")
MODEL           = "claude-sonnet-4-6"
MAX_TOKENS      = 4096
HISTORY_WINDOW  = 20  # последних пар сообщений в контексте

SYSTEM_PROMPT = """\
Ты — персональный ИИ-ассистент Timur'а, работающий через Telegram.
Ты помогаешь с программированием, настройкой VPS, изучением технологий и любыми другими задачами.
Перед каждым ответом пиши блок 🧠 Думаю: с кратким ходом рассуждений (2-4 шага),
затем блок 💬 Ответ: с финальным ответом.
Отвечай на русском языке. Будь конкретным и лаконичным.
"""

# ── Хранилище истории ────────────────────────────────────────────────────────
def load_history() -> list:
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []

def save_history(history: list):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def history_to_messages(history: list) -> list[dict]:
    """Конвертирует shared_history в формат Anthropic messages."""
    messages = []
    for entry in history[-HISTORY_WINDOW:]:
        messages.append({"role": "user",      "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["assistant"]})
    return messages

# ── Клиент Anthropic ─────────────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

_lock = asyncio.Lock()

async def ask_claude(user_text: str, history: list) -> str:
    messages = history_to_messages(history)
    messages.append({"role": "user", "content": user_text})

    loop = asyncio.get_event_loop()

    def _call():
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text

    return await loop.run_in_executor(None, _call)

# ── Хендлеры ────────────────────────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        return

    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = PHOTOS_DIR / f"photo_{timestamp}.jpg"
    await file.download_to_drive(path)

    caption = update.message.caption or ""
    caption_text = f" Подпись: {caption}" if caption else ""
    reply = f"📸 Фото сохранено: `{path}`{caption_text}\nMожешь спросить про него в следующем сообщении."
    await update.message.reply_text(reply, parse_mode="Markdown")

    history = load_history()
    history.append({
        "source": "telegram",
        "time": datetime.now().isoformat(),
        "user": f"[ФОТО: {path}]{caption_text}",
        "assistant": reply,
    })
    save_history(history)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        logging.warning(f"Отклонён пользователь {update.effective_user.id}")
        return

    user_text = update.message.text
    logging.info(f"Сообщение: {user_text[:80]}")

    if _lock.locked():
        await update.message.reply_text("⏳ Обрабатываю предыдущее сообщение...")
        return

    thinking_msg = await update.message.reply_text("🧠 Думаю...")

    async with _lock:
        try:
            history = load_history()
            reply = await asyncio.wait_for(
                ask_claude(user_text, history),
                timeout=120
            )
        except asyncio.TimeoutError:
            reply = "⏰ Превышено время ожидания (2 мин). Попробуй короче."
        except anthropic.AuthenticationError:
            reply = "❌ Неверный API ключ. Проверь ANTHROPIC_API_KEY в .env файле."
            logging.error("AuthenticationError — проверь API ключ")
        except Exception as e:
            reply = f"❌ Ошибка: {e}"
            logging.exception("Ошибка запроса к Claude")

    history = load_history()
    history.append({
        "source": "telegram",
        "time": datetime.now().isoformat(),
        "user": user_text,
        "assistant": reply,
    })
    save_history(history)

    # Отправляем ответ (разбиваем если > 4096 символов)
    chunks = [reply[i:i+4096] for i in range(0, len(reply), 4096)]
    await thinking_msg.edit_text(chunks[0])
    for chunk in chunks[1:]:
        await update.message.reply_text(chunk)


# ── Запуск ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not ANTHROPIC_KEY or ANTHROPIC_KEY == "ВСТАВЬ_СВОЙ_КЛЮЧ_СЮДА":
        logging.error("Не задан ANTHROPIC_API_KEY в .env файле!")
        logging.error("Получи ключ на https://console.anthropic.com/settings/keys")
        exit(1)

    logging.info(f"Запуск бота, модель: {MODEL}")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
