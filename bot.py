import os
import json
import logging
import tempfile
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from storage import Storage
from ocr import extract_text
from analyzer import analyze_text
from linker import find_related

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

storage = Storage()

ALLOWED_EXTENSIONS = {
    "pdf", "epub", "fb2", "djvu", "mobi", "txt",
    "doc", "docx", "azw", "azw3", "rtf",
}

# ─────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Assalomu alaykum, {user.first_name}!\n\n"
        "📚 *Kitob tahlil botiga xush kelibsiz.*\n\n"
        "Menga kitob faylini yuboring — bot uni:\n"
        "  🔍 OCR qiladi (matn chiqaradi)\n"
        "  🧠 Tahlil qiladi (kalit so'zlar, mavzu)\n"
        "  🔗 Oldingi kitoblar bilan bog'laydi\n\n"
        "📌 *Buyruqlar:*\n"
        "/list — kitoblar ro'yxati\n"
        "/search — qidirish\n"
        "/info <id> — kitob tahlilini ko'rish\n"
        "/stats — statistika\n"
        "/help — yordam"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ *Yordam*\n\n"
        "📤 *Kitob yuklash:* Faylni yuboring → OCR + tahlil avtomatik boshlanadi.\n\n"
        "📋 /list — barcha kitoblar\n"
        "🔍 /search <so'z> — kalit so'z bo'yicha qidirish\n"
        "📖 /info <id> — kitob tahlilini ko'rish\n"
        "📊 /stats — statistika\n\n"
        "📁 *Formatlar:* PDF · EPUB · FB2 · DJVU · TXT · DOC · DOCX\n\n"
        "🌐 *Tillar:* O'zbek (lotin & kirill) · Rus"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def list_books(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    books = storage.get_books(user_id)

    if not books:
        await update.message.reply_text("📭 Hozircha kitoblar yo'q. Birinchi kitobingizni yuboring!")
        return

    await update.message.reply_text(
        f"📚 *Sizning kitoblaringiz ({len(books)} ta):*", parse_mode="Markdown"
    )

    for book in books:
        analyzed_mark = "🧠" if book.get("analyzed") else "⏳"
        ext_emoji = _ext_emoji(book.get("extension", ""))
        size_str = _format_size(book.get("size", 0))

        keywords = _parse_list(book.get("keywords"))
        kw_str = ", ".join(keywords[:4]) if keywords else "—"

        keyboard = [
            [
                InlineKeyboardButton("📖 Tahlil", callback_data=f"info_{book['id']}"),
                InlineKeyboardButton("🔗 Bog'liqlar", callback_data=f"related_{book['id']}"),
                InlineKeyboardButton("❌", callback_data=f"delete_{book['id']}"),
            ]
        ]
        caption = (
            f"{analyzed_mark} {ext_emoji} *{book['title']}*\n"
            f"📁 {book.get('extension','?').upper()}  •  {size_str}  •  ID: `{book['id']}`\n"
            f"🏷 {kw_str}"
        )
        await update.message.reply_text(
            caption, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def book_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Misol: `/info 3`", parse_mode="Markdown")
        return
    try:
        book_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID raqam bo'lishi kerak.")
        return

    book = storage.get_book(user_id, book_id)
    if not book:
        await update.message.reply_text("Kitob topilmadi.")
        return

    await _send_book_analysis(update.message, book)


async def search_books(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await update.message.reply_text("Misol: `/search soliq`", parse_mode="Markdown")
        return

    results = storage.search_books(user_id, query)
    if not results:
        await update.message.reply_text(f"❌ *«{query}»* bo'yicha hech narsa topilmadi.", parse_mode="Markdown")
        return

    text = f"🔍 *«{query}»* — {len(results)} ta natija:\n\n"
    for b in results:
        kw = _parse_list(b.get("keywords"))
        text += f"{_ext_emoji(b.get('extension',''))} *{b['title']}* (ID: `{b['id']}`)\n"
        if kw:
            text += f"   🏷 {', '.join(kw[:4])}\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    info = storage.get_stats(user_id)
    books = storage.get_books(user_id)
    analyzed = sum(1 for b in books if b.get("analyzed"))

    text = (
        f"📊 *Statistika*\n\n"
        f"📚 Jami kitoblar: *{info['total']}* ta\n"
        f"🧠 Tahlil qilingan: *{analyzed}* ta\n"
        f"💾 Umumiy hajm: *{_format_size(info['total_size'])}*\n\n"
        f"📁 *Formatlar:*\n"
    )
    for ext, count in info["by_ext"].items():
        text += f"  {_ext_emoji(ext)} {ext.upper()}: {count} ta\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────
# FILE HANDLER — asosiy pipeline
# ─────────────────────────────────────────────

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document

    if not doc:
        await update.message.reply_text("⚠️ Fayl topilmadi.")
        return

    file_name = doc.file_name or "nomsiz"
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    if extension not in ALLOWED_EXTENSIONS:
        await update.message.reply_text(
            f"⚠️ *{extension.upper()}* formati qo'llab-quvvatlanmaydi.\n"
            "✅ PDF · EPUB · FB2 · DJVU · TXT · DOC · DOCX",
            parse_mode="Markdown",
        )
        return

    title = file_name.rsplit(".", 1)[0] if "." in file_name else file_name

    # 1. Bazaga saqlash
    book_id = storage.add_book(
        user_id=user_id,
        title=title,
        file_id=doc.file_id,
        extension=extension,
        size=doc.file_size or 0,
        file_name=file_name,
    )

    status_msg = await update.message.reply_text(
        f"✅ *{title}* saqlandi (ID: `{book_id}`)\n\n"
        f"⏳ OCR va tahlil boshlanmoqda...",
        parse_mode="Markdown",
    )

    # 2. Faylni yuklab olish
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp:
            tmp_path = tmp.name
        await tg_file.download_to_drive(tmp_path)
    except Exception as e:
        logger.error(f"Fayl yuklab olish xatosi: {e}")
        await status_msg.edit_text(
            f"✅ *{title}* saqlandi.\n⚠️ Fayl yuklab olinmadi: {e}",
            parse_mode="Markdown",
        )
        return

    # 3. OCR
    await status_msg.edit_text(
        f"🔍 *{title}*\n⏳ Matn chiqarilmoqda (OCR)...",
        parse_mode="Markdown",
    )
    raw_text = extract_text(tmp_path, extension)

    # Vaqtinchalik faylni o'chirish
    try:
        os.unlink(tmp_path)
    except Exception:
        pass

    if not raw_text.strip():
        await status_msg.edit_text(
            f"✅ *{title}* saqlandi.\n"
            f"⚠️ Matn chiqarib bo'lmadi (skanerlangan yoki himoyalangan bo'lishi mumkin).",
            parse_mode="Markdown",
        )
        return

    # 4. Tahlil
    await status_msg.edit_text(
        f"🧠 *{title}*\n⏳ Tahlil qilinmoqda...",
        parse_mode="Markdown",
    )
    analysis = analyze_text(raw_text, title)
    storage.save_analysis(book_id, analysis)

    # 5. Bog'liqlik
    await status_msg.edit_text(
        f"🔗 *{title}*\n⏳ Bog'liq kitoblar qidirilmoqda...",
        parse_mode="Markdown",
    )
    existing = storage.get_books_for_linking(user_id, book_id)
    related = find_related(analysis, existing)

    # 6. Natijani yuborish
    await status_msg.delete()
    await _send_analysis_result(update.message, title, book_id, analysis, related, doc.file_size or 0, extension)


# ─────────────────────────────────────────────
# CALLBACK HANDLER
# ─────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("delete_"):
        book_id = int(data.split("_", 1)[1])
        book = storage.get_book(user_id, book_id)
        if book:
            storage.delete_book(user_id, book_id)
            await query.edit_message_text(f"🗑 *{book['title']}* o'chirildi.", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Kitob topilmadi.")

    elif data.startswith("info_"):
        book_id = int(data.split("_", 1)[1])
        book = storage.get_book(user_id, book_id)
        if book:
            await _send_book_analysis(query.message, book)
        else:
            await query.edit_message_text("❌ Kitob topilmadi.")

    elif data.startswith("related_"):
        book_id = int(data.split("_", 1)[1])
        book = storage.get_book(user_id, book_id)
        if not book:
            await query.edit_message_text("❌ Kitob topilmadi.")
            return

        existing = storage.get_books_for_linking(user_id, book_id)
        analysis = {
            "keywords": _parse_list(book.get("keywords")),
            "topics": _parse_list(book.get("topics")),
            "raw_text": book.get("raw_text", ""),
        }
        related = find_related(analysis, existing)
        await _send_related(query.message, book["title"], related)


# ─────────────────────────────────────────────
# XABAR FORMATLASH
# ─────────────────────────────────────────────

async def _send_analysis_result(message, title, book_id, analysis, related, size, extension):
    keywords = analysis.get("keywords", [])
    topics = analysis.get("topics", [])
    summary = analysis.get("summary", "")
    language = analysis.get("language", "")

    lang_map = {
        "uzbek_latin": "🇺🇿 O'zbek (lotin)",
        "uzbek_cyrillic": "🇺🇿 O'zbek (kirill)",
        "russian": "🇷🇺 Rus",
        "mixed": "🌐 Aralash",
    }

    text = (
        f"✅ *{title}*\n"
        f"ID: `{book_id}`  •  {_ext_emoji(extension)} {extension.upper()}  •  {_format_size(size)}\n"
        f"🌐 Til: {lang_map.get(language, language or '—')}\n\n"
        f"📝 *Xulosa:*\n{summary}\n\n"
        f"🏷 *Kalit so'zlar:*\n{', '.join(keywords) if keywords else '—'}\n\n"
        f"📂 *Mavzular:*\n{', '.join(topics) if topics else '—'}\n"
    )

    if related:
        text += f"\n🔗 *Bog'liq kitoblar ({len(related)} ta):*\n"
        for r in related:
            pct = int(r["score"] * 100)
            text += f"  • *{r['title']}* — {pct}% o'xshash\n"
            text += f"    _{r['reason']}_\n"
    else:
        text += "\n🔗 *Bog'liq kitoblar:* hozircha yo'q."

    await message.reply_text(text, parse_mode="Markdown")


async def _send_book_analysis(message, book: dict):
    keywords = _parse_list(book.get("keywords"))
    topics = _parse_list(book.get("topics"))

    lang_map = {
        "uzbek_latin": "🇺🇿 O'zbek (lotin)",
        "uzbek_cyrillic": "🇺🇿 O'zbek (kirill)",
        "russian": "🇷🇺 Rus",
        "mixed": "🌐 Aralash",
    }

    if not book.get("analyzed"):
        await message.reply_text(
            f"⏳ *{book['title']}* hali tahlil qilinmagan.\n"
            "Faylni qayta yuboring.",
            parse_mode="Markdown",
        )
        return

    text = (
        f"📖 *{book['title']}*\n"
        f"ID: `{book['id']}`  •  {book.get('date','')}\n"
        f"🌐 {lang_map.get(book.get('language',''), book.get('language','—'))}\n\n"
        f"📝 *Xulosa:*\n{book.get('summary') or '—'}\n\n"
        f"🏷 *Kalit so'zlar:*\n{', '.join(keywords) if keywords else '—'}\n\n"
        f"📂 *Mavzular:*\n{', '.join(topics) if topics else '—'}"
    )
    await message.reply_text(text, parse_mode="Markdown")


async def _send_related(message, title: str, related: list):
    if not related:
        await message.reply_text(f"🔗 *{title}* uchun bog'liq kitoblar topilmadi.", parse_mode="Markdown")
        return

    text = f"🔗 *{title}* — bog'liq kitoblar:\n\n"
    for r in related:
        pct = int(r["score"] * 100)
        text += f"📗 *{r['title']}* — {pct}% o'xshash\n"
        text += f"   _{r['reason']}_\n\n"

    await message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _ext_emoji(ext: str) -> str:
    return {
        "pdf": "📕", "epub": "📗", "fb2": "📘",
        "djvu": "📙", "txt": "📄", "mobi": "📱",
        "doc": "📝", "docx": "📝",
    }.get((ext or "").lower(), "📖")


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    return f"{size_bytes / 1024 ** 3:.1f} GB"


def _parse_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return []
    return []


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN topilmadi! .env faylini tekshiring.")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("list", list_books))
    app.add_handler(CommandHandler("search", search_books))
    app.add_handler(CommandHandler("info", book_info))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
