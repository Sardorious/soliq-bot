"""
analyzer.py — Matnni tahlil qilish.

Claude API bo'lsa: chuqur semantik tahlil.
Bo'lmasa: TF-IDF + atama lug'ati + mavzu klassifikatori.
"""

import os
import json
import logging
import re
from typing import Dict, List
from collections import Counter

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
ANALYSIS_CHUNK = 6000

# ─────────────────────────────────────────────────────────────
# MAVZU LUG'ATI — har mavzuga xos atamalar
# O'zbek (lotin + kirill) va Rus tilida
# ─────────────────────────────────────────────────────────────
TOPIC_KEYWORDS = {
    "Soliq va moliya": [
        "soliq", "soliqa", "daromad", "qqs", "aksiz", "stavka", "byudjet",
        "to'lov", "tolov", "imtiyoz", "chegirma", "hisobot", "deklaratsiya",
        "inspeksiya", "audit", "moliya", "kredit", "dividend", "foyda",
        "налог", "доход", "бюджет", "ндс", "акциз", "ставка", "льгота",
        "вычет", "декларация", "инспекция", "финансы", "прибыль",
    ],
    "Mehnat va ish haqi": [
        "mehnat", "ish haqi", "ishchi", "xodim", "ish joyi", "bandlik",
        "nafaqa", "ta'til", "ishdan bo'shatish", "shartnoma", "jamoa",
        "труд", "зарплата", "работник", "сотрудник", "занятость",
        "отпуск", "увольнение", "договор", "пенсия", "пособие",
    ],
    "Tadbirkorlik va biznes": [
        "tadbirkor", "korxona", "firma", "kompaniya", "ro'yxatdan",
        "litsenziya", "patent", "savdo", "import", "eksport", "investitsiya",
        "предприниматель", "предприятие", "компания", "регистрация",
        "лицензия", "торговля", "инвестиция", "бизнес",
    ],
    "Huquq va qonunchilik": [
        "qonun", "kodeks", "farmon", "qaror", "nizom", "tartib", "tartib-qoida",
        "huquq", "majburiyat", "javobgarlik", "jarima", "sanksiya", "sud",
        "закон", "кодекс", "указ", "постановление", "устав", "право",
        "обязанность", "ответственность", "штраф", "санкция", "суд",
    ],
    "Yer va mulk": [
        "yer", "er", "mulk", "ko'chmas mulk", "ijara", "ijaraga", "kadastr",
        "arenda", "uy", "bino", "inshoot", "dala", "qishloq",
        "земля", "имущество", "недвижимость", "аренда", "кадастр",
        "здание", "сооружение",
    ],
    "Ta'lim va fan": [
        "ta'lim", "maktab", "universitet", "ilm", "fan", "tadqiqot",
        "diplom", "malaka", "o'qituvchi", "talaba", "bilim",
        "образование", "школа", "университет", "наука", "исследование",
        "диплом", "квалификация", "учитель", "студент",
    ],
    "Sog'liqni saqlash": [
        "tibbiyot", "sog'liq", "kasallik", "dori", "shifoxona", "vrach",
        "sugurta", "sug'urta", "sanatoriya", "reabilitatsiya",
        "медицина", "здоровье", "болезнь", "лекарство", "больница",
        "врач", "страховка", "санаторий",
    ],
    "Raqamli texnologiyalar": [
        "axborot", "texnologiya", "raqamli", "elektron", "internet",
        "dastur", "tizim", "platforma", "ma'lumot", "kibxavfsizlik",
        "информация", "технология", "цифровой", "электронный",
        "программа", "система", "платформа", "данные", "кибербезопасность",
    ],
    "Atrof-muhit": [
        "ekologiya", "atrof-muhit", "tabiat", "chiqindi", "ifloslantirish",
        "suv", "havo", "yer osti", "qayta ishlash",
        "экология", "окружающая среда", "природа", "отходы",
        "загрязнение", "вода", "воздух", "переработка",
    ],
    "Qurilish va infratuzilma": [
        "qurilish", "bino", "loyiha", "norma", "standart", "kommunal",
        "yo'l", "ko'prik", "transport", "infratuzilma",
        "строительство", "здание", "проект", "норма", "стандарт",
        "коммунальный", "дорога", "мост", "транспорт",
    ],
}

# Ma'nosiz fe'l/ko'makchi so'zlar — kalit so'zdan chiqariladi
FUNCTIONAL_WORDS = {
    # O'zbek
    "va", "bu", "ham", "bilan", "uchun", "lekin", "yoki", "emas",
    "bir", "kerak", "qilish", "shu", "hamma", "u", "men", "sen",
    "biz", "ular", "har", "ko'p", "olish", "berish", "etish",
    "bo'lish", "qiladi", "etadi", "beradi", "oladi", "boradi",
    "keladi", "turadi", "edi", "ekan", "emish", "dir", "dagi",
    "dagi", "kabi", "singari", "orqali", "tomon", "qadar",
    "miqdorda", "belgilanadi", "amalga", "oshiriladi", "hisoblanadi",
    "ko'rsatiladi", "taqdim", "topshiradi", "qo'llaniladi",
    "respublikasining", "o'zbekiston", "respublikasi",
    # Rus
    "и", "в", "не", "на", "что", "с", "а", "как", "это", "то",
    "по", "из", "к", "за", "от", "но", "же", "он", "она", "они",
    "мы", "вы", "я", "был", "была", "были", "быть", "при", "или",
    "об", "так", "его", "её", "их", "для", "до", "со", "во",
    "также", "более", "если", "когда", "который", "которая",
    "которые", "этот", "эта", "эти", "том", "тем", "может",
    "должен", "является", "осуществляется", "устанавливается",
    "предусмотрено", "установлено", "согласно", "настоящего",
}


def analyze_text(text: str, title: str = "") -> Dict:
    if not text or len(text.strip()) < 50:
        return _empty_result()

    chunk = text[:ANALYSIS_CHUNK]

    if ANTHROPIC_API_KEY:
        result = _analyze_with_claude(chunk, title)
    else:
        result = _analyze_smart(chunk, title)

    result["raw_text"] = text[:50000]
    return result


# ─────────────────────────────────────────────
# CLAUDE API TAHLIL
# ─────────────────────────────────────────────

def _analyze_with_claude(text: str, title: str) -> Dict:
    prompt = f"""Quyidagi huquqiy/rasmiy hujjat matnini tahlil qil.

Kitob/hujjat nomi: {title}

Matn:
{text}

FAQAT JSON formatida javob ber (boshqa hech narsa yozma):
{{
  "keywords": ["atama1", "atama2", ...],
  "topics": ["mavzu1", "mavzu2", ...],
  "summary": "2-3 gaplik qisqa mazmun",
  "language": "uzbek_latin" | "uzbek_cyrillic" | "russian" | "mixed"
}}

Qoidalar:
- keywords: 10-15 ta. Faqat ma'noli atamalar (ot, sifat). Fe'llar, yordamchi so'zlar, "respublikasi", "o'zbekiston" KIRMASIN.
- topics: 3-5 ta keng mavzu/soha (masalan: "Soliq va moliya", "Mehnat huquqi", "Tadbirkorlik").
- summary: hujjatning asosiy mohiyati.
- Kalit so'zlar hujjat tilida bo'lsin."""

    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        response.raise_for_status()
        raw = response.json()["content"][0]["text"]
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)
        return {
            "keywords": data.get("keywords", [])[:15],
            "topics":   data.get("topics", [])[:5],
            "summary":  data.get("summary", ""),
            "language": data.get("language", "unknown"),
        }
    except Exception as e:
        logger.warning(f"Claude API xatosi: {e}")
        return _analyze_smart(text, title)


# ─────────────────────────────────────────────
# AQLLI STATISTIK TAHLIL (API siz)
# ─────────────────────────────────────────────

def _analyze_smart(text: str, title: str) -> Dict:
    """
    TF-IDF + atama lug'ati asosida tahlil.
    1. Faqat ot/atama bo'lgan so'zlarni oladi
    2. Mavzu lug'ati bilan bog'liqlikni hisoblaydi
    3. Ma'noli kalit so'zlar chiqaradi
    """

    # ── 1. So'zlarni chiqarish ──────────────────
    words = re.findall(r"[a-zA-ZÀ-ÿа-яА-ЯёЁ'ʻ\u02bb]{3,}", text.lower())
    words = [w for w in words if w not in FUNCTIONAL_WORDS]

    # Bigram (2 so'zli atamalar) ham olish
    all_words = re.findall(r"[a-zA-ZÀ-ÿа-яА-ЯёЁ'ʻ\u02bb]{3,}", text.lower())
    bigrams = [
        all_words[i] + " " + all_words[i+1]
        for i in range(len(all_words)-1)
        if all_words[i] not in FUNCTIONAL_WORDS and all_words[i+1] not in FUNCTIONAL_WORDS
    ]

    word_freq = Counter(words)
    bigram_freq = Counter(bigrams)

    # ── 2. TF-IDF vazni: noyob so'zlarga ustunlik ──
    total = len(words) or 1
    scored = {}
    for word, freq in word_freq.items():
        tf = freq / total
        # Noyob (kam uchragan) va ma'noli so'zlarga yuqori ball
        length_bonus = min(len(word) / 10, 0.3)  # Uzun so'z = atama ehtimoli yuqori
        scored[word] = tf * (1 + length_bonus)

    # Bigramlar uchun alohida score
    for bigram, freq in bigram_freq.items():
        if freq >= 2:  # Kamida 2 marta uchragan bigram
            scored[bigram] = (freq / total) * 2.0

    # ── 3. Mavzu lug'ati bilan bonus ──────────────
    topic_matches = {}
    for topic, topic_words in TOPIC_KEYWORDS.items():
        score = 0
        matched = []
        for tw in topic_words:
            if tw in text.lower():
                freq = text.lower().count(tw)
                score += freq
                matched.append(tw)
                # Lug'atdagi atamaga bonus
                if tw in scored:
                    scored[tw] = scored[tw] * 2.0
        if score > 0:
            topic_matches[topic] = {"score": score, "matched": matched}

    # ── 4. Kalit so'zlar — top scored, ma'noli ────
    # Qo'shimcha filtr: faqat atama bo'lishi mumkin bo'lganlar
    meaningful = {
        w: s for w, s in scored.items()
        if _is_meaningful(w)
    }

    keywords = [w for w, _ in sorted(meaningful.items(), key=lambda x: -x[1])[:15]]

    # ── 5. Mavzular — eng ko'p mos kelganlar ──────
    if topic_matches:
        topics = [
            t for t, _ in sorted(topic_matches.items(), key=lambda x: -x[1]["score"])[:5]
        ]
    else:
        # Lug'atda topilmasa — eng ko'p uchragan so'z guruhlari
        topics = _guess_topics(keywords)

    # ── 6. Til aniqlash ───────────────────────────
    language = _detect_language(text)

    summary = _make_summary(title, keywords, topics, len(text.split()))

    return {
        "keywords": keywords,
        "topics":   topics,
        "summary":  summary,
        "language": language,
    }


def _is_meaningful(word: str) -> bool:
    """So'z ma'noli atama ekanligini tekshiradi."""
    # Juda qisqa
    if len(word) < 3:
        return False
    # Faqat raqam
    if word.isdigit():
        return False
    # Funksional so'z
    if word in FUNCTIONAL_WORDS:
        return False
    # Fe'l qo'shimchalari bilan tugagan o'zbek fe'llari
    uz_verb_endings = ("ladi", "ydi", "adi", "edi", "ish", "moq", "iladi", "lanadi")
    if any(word.endswith(e) for e in uz_verb_endings) and len(word) > 7:
        return False
    # Rus fe'l qo'shimchalari
    ru_verb_endings = ("ется", "ится", "ются", "иться", "ться", "ивать", "овать")
    if any(word.endswith(e) for e in ru_verb_endings):
        return False
    return True


def _guess_topics(keywords: list) -> list:
    """Kalit so'zlar asosida mavzu taxmin qiladi."""
    if not keywords:
        return ["Umumiy"]
    # Birinchi 3 ta ma'noli kalit so'zni mavzu sifatida qaytarish
    return keywords[:3]


def _detect_language(text: str) -> str:
    cyrillic = len(re.findall(r"[а-яёА-ЯЁ]", text))
    latin    = len(re.findall(r"[a-zA-Z]", text))
    uz_chars = len(re.findall(r"[oʻgʻO'G']", text))

    if cyrillic > latin * 1.5:
        return "uzbek_cyrillic" if uz_chars > 5 else "russian"
    elif latin > cyrillic:
        return "uzbek_latin"
    return "mixed"


def _make_summary(title: str, keywords: list, topics: list, word_count: int) -> str:
    kw = ", ".join(keywords[:5]) if keywords else "—"
    tp = ", ".join(topics[:3]) if topics else "—"
    return (
        f"«{title}» hujjati {word_count} so'zdan iborat. "
        f"Asosiy mavzular: {tp}. "
        f"Asosiy atamalar: {kw}."
    )


def _empty_result() -> Dict:
    return {
        "keywords": [],
        "topics":   [],
        "summary":  "Matn chiqarilmadi yoki juda qisqa.",
        "language": "unknown",
        "raw_text": "",
    }