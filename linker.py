"""
linker.py — Kitoblar orasidagi bog'liqlikni hisoblash.

Usullar:
  1. Kalit so'zlar kesishmasi (Jaccard similarity)
  2. Mavzu/tema o'xshashligi
  3. TF-IDF + cosine similarity (matn mavjud bo'lsa)

Qaytaradi: bog'liq kitoblar ro'yxati (score bilan)
"""

import logging
import json
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# Minimal o'xshashlik chegarasi (0.0 - 1.0)
MIN_SIMILARITY = 0.15
# Qaytariladigan max bog'liq kitoblar soni
TOP_N = 5


def find_related(
    new_book: Dict,
    existing_books: List[Dict],
) -> List[Dict]:
    """
    new_book — yangi yuklangan kitob (analysis natijasi bilan)
    existing_books — bazadagi boshqa kitoblar

    Qaytaradi: [{"id", "title", "score", "reason"}, ...]
    """
    if not existing_books:
        return []

    results = []

    new_keywords = set(k.lower() for k in new_book.get("keywords", []))
    new_topics = set(t.lower() for t in new_book.get("topics", []))
    new_text = new_book.get("raw_text", "")

    for book in existing_books:
        book_keywords = set(k.lower() for k in _parse_json_field(book.get("keywords")))
        book_topics = set(t.lower() for t in _parse_json_field(book.get("topics")))
        book_text = book.get("raw_text", "")

        scores = []
        reasons = []

        # 1. Kalit so'zlar Jaccard similarity
        kw_score = _jaccard(new_keywords, book_keywords)
        if kw_score > 0:
            scores.append(kw_score * 0.5)
            common_kw = new_keywords & book_keywords
            if common_kw:
                reasons.append(f"umumiy kalit so'zlar: {', '.join(list(common_kw)[:5])}")

        # 2. Mavzu o'xshashligi
        topic_score = _jaccard(new_topics, book_topics)
        if topic_score > 0:
            scores.append(topic_score * 0.4)
            common_topics = new_topics & book_topics
            if common_topics:
                reasons.append(f"umumiy mavzular: {', '.join(list(common_topics)[:3])}")

        # 3. TF-IDF cosine similarity (agar matn mavjud bo'lsa)
        if new_text and book_text and len(new_text) > 200 and len(book_text) > 200:
            cos_score = _cosine_similarity(new_text, book_text)
            if cos_score > 0.05:
                scores.append(cos_score * 0.3)

        if not scores:
            continue

        total_score = min(sum(scores), 1.0)

        if total_score >= MIN_SIMILARITY:
            results.append({
                "id": book["id"],
                "title": book["title"],
                "score": round(total_score, 3),
                "reason": "; ".join(reasons) if reasons else "mazmun o'xshashligi",
            })

    # Yuqori scoreli kitoblarni oldingi chiqarish
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:TOP_N]


def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _cosine_similarity(text_a: str, text_b: str) -> float:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        # Har biridan max 5000 belgi
        a = text_a[:5000]
        b = text_b[:5000]

        vectorizer = TfidfVectorizer(
            max_features=500,
            min_df=1,
            analyzer="word",
            token_pattern=r"[a-zA-Zа-яА-ЯёЁ'ʻ]{3,}",
        )
        tfidf = vectorizer.fit_transform([a, b])
        score = cosine_similarity(tfidf[0], tfidf[1])[0][0]
        return float(score)
    except Exception as e:
        logger.warning(f"Cosine similarity xatosi: {e}")
        return 0.0


def _parse_json_field(value) -> list:
    """DB dan kelgan JSON string yoki list ni parse qiladi."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return []
    return []
