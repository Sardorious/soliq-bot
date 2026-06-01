"""
scraper.py — lex.uz va boshqa huquqiy saytlardan matn olish.

Qo'llab-quvvatlanadigan URL formatlar:
  https://lex.uz/docs/1234567
  https://lex.uz/uz/docs/1234567
  https://lex.uz/ru/docs/1234567
  https://lex.uz/docs/-1234567   (manfiy ID ham bo'ladi)
"""

import re
import logging
import httpx
from bs4 import BeautifulSoup
from typing import Optional, Dict

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uz-UZ,uz;q=0.9,ru;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

TIMEOUT = 20


def is_supported_url(url: str) -> bool:
    """URL qo'llab-quvvatlanadimi?"""
    return bool(re.search(r"lex\.uz", url, re.IGNORECASE))


def scrape(url: str) -> Dict:
    """
    URL dan matn va sarlavha oladi.
    Qaytaradi: {"title": str, "text": str, "url": str, "error": str|None}
    """
    url = url.strip()

    if "lex.uz" in url:
        return _scrape_lex(url)

    return {"title": "", "text": "", "url": url, "error": "Qo'llab-quvvatlanmagan sayt"}


def _scrape_lex(url: str) -> Dict:
    """lex.uz dan hujjat matnini olish."""

    # URL ni normallashtirish
    doc_id = _extract_lex_id(url)
    if not doc_id:
        return {
            "title": "", "text": "", "url": url,
            "error": "URL dan hujjat ID si topilmadi. Misol: https://lex.uz/docs/6453686"
        }

    # Turli til versiyalarini sinab ko'rish
    candidate_urls = [
        f"https://lex.uz/docs/{doc_id}",
        f"https://lex.uz/uz/docs/{doc_id}",
        f"https://lex.uz/ru/docs/{doc_id}",
    ]

    last_error = None
    for try_url in candidate_urls:
        try:
            result = _fetch_lex_page(try_url)
            if result and result.get("text"):
                result["url"] = try_url
                return result
        except Exception as e:
            last_error = str(e)
            logger.warning(f"lex.uz fetch xatosi ({try_url}): {e}")

    return {
        "title": "", "text": "", "url": url,
        "error": "Sahifa ochilmadi: " + str(last_error or "noma'lum xato") + ". Server lex.uz ga kira olmasligi mumkin."
    }


def _fetch_lex_page(url: str) -> Optional[Dict]:
    """Sahifani yuklab matnni ajratadi."""
    with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        resp = client.get(url)

    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.text, "lxml")

    # Sarlavha
    title = _extract_title(soup)

    # Matn — lex.uz dagi mumkin bo'lgan konteynerlar
    text = ""
    selectors = [
        "#document-view",
        ".document-text",
        ".doc-content",
        ".lex-content",
        "#doc-text",
        ".act-text",
        "article",
        "main",
        ".content",
    ]

    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            # Script va style teglarini olib tashlash
            for tag in el(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 200:
                break

    # Agar hech narsa topilmasa — butun body dan olish
    if len(text) < 200:
        body = soup.find("body")
        if body:
            for tag in body(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            text = body.get_text(separator="\n", strip=True)

    # Bo'sh qatorlarni tozalash
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) < 100:
        return None

    return {"title": title, "text": text}


def _extract_title(soup: BeautifulSoup) -> str:
    """Sahifa sarlavhasini olish."""
    # lex.uz sarlavha joylari
    for sel in ["h1.doc-title", ".document-title", "h1", "title"]:
        el = soup.select_one(sel)
        if el:
            t = el.get_text(strip=True)
            if t and len(t) > 5:
                return t[:200]
    return "lex.uz hujjati"


def _extract_lex_id(url: str) -> Optional[str]:
    """
    URL dan hujjat ID sini ajratadi.
    https://lex.uz/docs/6453686                → 6453686
    https://lex.uz/uz/docs/-5871129            → -5871129
    https://lex.uz/pages/getact?actid=6453686  → 6453686
    """
    # /docs/ID format
    m = re.search(r"/docs/(-?\d+)", url)
    if m:
        return m.group(1)
    # ?actid=ID format
    m = re.search(r"actid=(-?\d+)", url)
    if m:
        return m.group(1)
    return None
