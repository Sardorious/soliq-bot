"""
analyzer.py — Matnni Claude AI orqali tahlil qilish.

Qaytaradi:
  - keywords: list[str]       — 10-15 ta kalit so'z
  - topics: list[str]         — 3-5 ta mavzu/tema
  - summary: str              — qisqa xulosa (2-3 gap)
  - language: str             — aniqlangar til
  - embedding: list[float]    — TF-IDF vektori (bog'liqlik uchun)
"""

import os
import json
import logging
import re
from typing import Dict, List

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"

# Tahlil uchun matndan nechta belgi yuboriladi
ANALYSIS_CHUNK = 6000


def analyze_text(text: str, title: str = "") -> Dict:
    """
    Matnni tahlil qiladi.
    Qaytaradi: {keywords, topics, summary, language, raw_text}
    """
    if not text or len(text.strip()) < 100:
        return _empty_result()

    chunk = text[:ANALYSIS_CHUNK]

    if ANTHROPIC_API_KEY:
        result = _analyze_with_claude(chunk, title)
    else:
        # Claude API yo'q bo'lsa — oddiy statistik usul
        result = _analyze_simple(chunk, title)

    result["raw_text"] = text[:50000]  # bog'liqlik hisoblash uchun
    return result


def _analyze_with_claude(text: str, title: str) -> Dict:
    """Claude API orqali chuqur tahlil."""
    prompt = f"""Quyidagi kitob matni berilgan. Uni tahlil qil va FAQAT JSON formatida javob ber.

Kitob nomi: {title}

Matn:
{text}

JSON formatida qaytarish kerak (boshqa hech narsa yozma):
{{
  "keywords": ["kalit_soz1", "kalit_soz2", ...],  // 10-15 ta, asosiy atama va tushunchalar
  "topics": ["mavzu1", "mavzu2", ...],              // 3-5 ta umumiy mavzu/soha
  "summary": "2-3 gaplik qisqa mazmun",
  "language": "uzbek_latin" | "uzbek_cyrillic" | "russian" | "mixed"
}}

Muhim: kalit so'zlar kitob tilida bo'lsin."""

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

        # JSON ni tozalab parse qilish
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)

        return {
            "keywords": data.get("keywords", [])[:15],
            "topics": data.get("topics", [])[:5],
            "summary": data.get("summary", ""),
            "language": data.get("language", "unknown"),
        }
    except Exception as e:
        logger.warning(f"Claude API xatosi: {e}")
        return _analyze_simple(text, title)


def _analyze_simple(text: str, title: str) -> Dict:
    """
    Claude API siz — TF-IDF asosida kalit so'z ajratish.
    O'zbek, kirill, rus uchun ishlaydi.
    """
    import re
    from collections import Counter

    # Stopwords (o'zbek + rus)
    stopwords = {
        # O'zbek
        "va", "bu", "ham", "bilan", "uchun", "lekin", "yoki", "emas",
        "bir", "bo'lib", "bo'lgan", "kerak", "qilish", "shu", "hamma",
        "u", "men", "sen", "biz", "ular", "o'z", "har", "ko'p",
        # Rus
        "и", "в", "не", "на", "что", "с", "а", "как", "это", "то",
        "по", "из", "к", "за", "от", "но", "же", "он", "она", "они",
        "мы", "вы", "я", "был", "была", "были", "быть", "при", "или",
        "об", "так", "его", "её", "их", "для", "до", "со", "во",
    }

    # So'zlarni ajratish (lotin, kirill)
    words = re.findall(r"[a-zA-ZÀ-ÿа-яА-ЯёЁ'ʻ]{4,}", text.lower())
    words = [w for w in words if w not in stopwords]

    counter = Counter(words)
    keywords = [w for w, _ in counter.most_common(15)]

    # Til aniqlash
    cyrillic = len(re.findall(r"[а-яА-ЯёЁ]", text))
    latin = len(re.findall(r"[a-zA-Z]", text))
    uzbek_markers = len(re.findall(r"[oʻgʻ']", text))

    if cyrillic > latin * 2:
        lang = "russian" if uzbek_markers < 10 else "uzbek_cyrillic"
    elif latin > cyrillic:
        lang = "uzbek_latin"
    else:
        lang = "mixed"

    # Mavzular — eng ko'p uchragan so'z guruhlari
    topics = keywords[:5] if keywords else ["aniqlanmadi"]

    return {
        "keywords": keywords,
        "topics": topics,
        "summary": f"'{title}' — {len(text.split())} so'z. Asosiy atamalar: {', '.join(keywords[:5])}.",
        "language": lang,
    }


def _empty_result() -> Dict:
    return {
        "keywords": [],
        "topics": [],
        "summary": "Matn chiqarilmadi yoki juda qisqa.",
        "language": "unknown",
        "raw_text": "",
    }
