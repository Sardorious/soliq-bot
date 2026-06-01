# 📚 Kitob Bot

Telegram orqali kitoblarni saqlash va boshqarish uchun bot.

## Xususiyatlar

- 📤 Kitob fayllarini qabul qilish (PDF, EPUB, FB2, DJVU, MOBI, TXT, DOC, DOCX)
- 📋 Kitoblar ro'yxatini ko'rish
- 🔍 Nom bo'yicha qidirish
- 🗑 Kitobni o'chirish
- 📊 Statistika (jami kitob, umumiy hajm, formatlar)

## O'rnatish

### 1. Reponi klonlash

```bash
git clone https://github.com/username/kitob-bot.git
cd kitob-bot
```

### 2. Virtual muhit yaratish

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
# yoki
venv\Scripts\activate           # Windows
```

### 3. Kutubxonalarni o'rnatish

```bash
pip install -r requirements.txt
```

### 4. `.env` faylini sozlash

```bash
cp .env.example .env
```

`.env` faylini oching va tokenni qo'shing:

```
BOT_TOKEN=1234567890:ABCdef...
```

Token olish uchun Telegramda [@BotFather](https://t.me/BotFather) ga yozing.

### 5. Botni ishga tushirish

```bash
python bot.py
```

## Buyruqlar

| Buyruq | Tavsif |
|--------|--------|
| `/start` | Botni boshlash |
| `/list` | Barcha kitoblarni ko'rish |
| `/search <nom>` | Kitob qidirish |
| `/stats` | Statistika |
| `/help` | Yordam |

## Ma'lumotlar saqlash

Kitoblar fayllari Telegram serverlarida saqlanadi.  
Bot faqat `file_id`, nom, format va hajmni SQLite bazasiga yozadi (`books.db`).

## Texnologiyalar

- Python 3.10+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 21.x
- SQLite (ma'lumotlar bazasi)
- python-dotenv (muhit o'zgaruvchilari)
