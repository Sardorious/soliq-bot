import os
import logging
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

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

storage = Storage()


# ─────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Assalomu alaykum, {user.first_name}!\n\n"
        "📚 *Kitob saqlash botiga xush kelibsiz.*\n\n"
        "Menga istalgan kitob faylini yuboring — PDF, EPUB, FB2, DJVU va boshqalar.\n\n"
        "📌 *Buyruqlar:*\n"
        "/list — barcha kitoblar ro'yxati\n"
        "/search — kitob qidirish\n"
        "/stats — statistika\n"
        "/help — yordam"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ *Yordam*\n\n"
        "📤 *Kitob yuklash:* Faylni to'g'ridan-to'g'ri botga yuboring.\n"
        "   Fayl nomi, turi va hajmi avtomatik saqlanadi.\n\n"
        "📋 *Ro'yxat:* /list — barcha kitoblarni ko'rish\n\n"
        "🔍 *Qidirish:* /search <nom> — kitob nomini qidirish\n"
        "   Misol: `/search Navoiy`\n\n"
        "📊 *Statistika:* /stats — nechta kitob borligini ko'rish\n\n"
        "🗑 *O'chirish:* Ro'yxatda kitob yonidagi ❌ tugmasini bosing.\n\n"
        "📁 *Qo'llab-quvvatlanadigan formatlar:*\n"
        "PDF · EPUB · FB2 · DJVU · MOBI · TXT · DOC · DOCX"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def list_books(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    books = storage.get_books(user_id)

    if not books:
        await update.message.reply_text(
            "📭 Hozircha kitoblar yo'q.\nBirinchi kitobingizni yuboring!"
        )
        return

    await update.message.reply_text(
        f"📚 *Sizning kitoblaringiz ({len(books)} ta):*",
        parse_mode="Markdown",
    )

    for book in books:
        keyboard = [[InlineKeyboardButton("❌ O'chirish", callback_data=f"delete_{book['id']}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        ext_emoji = _ext_emoji(book.get("extension", ""))
        size_str = _format_size(book.get("size", 0))
        caption = (
            f"{ext_emoji} *{book['title']}*\n"
            f"📁 {book.get('extension', '?').upper()}  •  {size_str}\n"
            f"📅 {book.get('date', '—')}"
        )
        await update.message.reply_text(
            caption, parse_mode="Markdown", reply_markup=reply_markup
        )


async def search_books(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = " ".join(context.args).strip() if context.args else ""

    if not query:
        await update.message.reply_text(
            "🔍 Qidirish uchun nom kiriting:\n`/search Navoiy`",
            parse_mode="Markdown",
        )
        return

    results = storage.search_books(user_id, query)

    if not results:
        await update.message.reply_text(f"❌ *«{query}»* bo'yicha hech narsa topilmadi.", parse_mode="Markdown")
        return

    text = f"🔍 *«{query}»* bo'yicha {len(results)} ta natija:\n\n"
    for b in results:
        ext_emoji = _ext_emoji(b.get("extension", ""))
        text += f"{ext_emoji} {b['title']} — {b.get('extension','').upper()}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    info = storage.get_stats(user_id)
    text = (
        f"📊 *Statistika*\n\n"
        f"📚 Jami kitoblar: *{info['total']}* ta\n"
        f"💾 Jami hajm: *{_format_size(info['total_size'])}*\n\n"
        f"📁 *Formatlar bo'yicha:*\n"
    )
    for ext, count in info["by_ext"].items():
        text += f"  {_ext_emoji(ext)} {ext.upper()}: {count} ta\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────
# FILE HANDLER
# ─────────────────────────────────────────────

ALLOWED_EXTENSIONS = {
    "pdf", "epub", "fb2", "djvu", "mobi", "txt",
    "doc", "docx", "azw", "azw3", "lit", "rtf",
}


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document

    if not doc:
        await update.message.reply_text("⚠️ Fayl topilmadi. Iltimos, kitob faylini yuboring.")
        return

    file_name = doc.file_name or "nomsiz"
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    if extension not in ALLOWED_EXTENSIONS:
        await update.message.reply_text(
            f"⚠️ *{extension.upper()}* formati qo'llab-quvvatlanmaydi.\n\n"
            "✅ Qabul qilinadiganlar: PDF, EPUB, FB2, DJVU, MOBI, TXT, DOC, DOCX",
            parse_mode="Markdown",
        )
        return

    # file_id saqlash (Telegram serverida saqlanadi, biz faqat ID saqlaymiz)
    file_id = doc.file_id
    size = doc.file_size or 0

    # Sarlavhani fayl nomidan olish
    title = file_name.rsplit(".", 1)[0] if "." in file_name else file_name

    book_id = storage.add_book(
        user_id=user_id,
        title=title,
        file_id=file_id,
        extension=extension,
        size=size,
        file_name=file_name,
    )

    ext_emoji = _ext_emoji(extension)
    await update.message.reply_text(
        f"✅ *Saqlandi!*\n\n"
        f"{ext_emoji} {title}\n"
        f"📁 {extension.upper()}  •  {_format_size(size)}\n\n"
        f"📚 Jami: {storage.get_book_count(user_id)} ta kitob",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────
# CALLBACK: O'CHIRISH
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
            await query.edit_message_text(
                f"🗑 *{book['title']}* o'chirildi.",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("❌ Kitob topilmadi yoki allaqachon o'chirilgan.")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _ext_emoji(ext: str) -> str:
    mapping = {
        "pdf": "📕", "epub": "📗", "fb2": "📘",
        "djvu": "📙", "txt": "📄", "mobi": "📱",
        "doc": "📝", "docx": "📝",
    }
    return mapping.get(ext.lower(), "📖")


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    return f"{size_bytes / 1024 ** 3:.1f} GB"


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
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
