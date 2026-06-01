"""
ocr.py — Fayldan matn chiqarish moduli.

Ustuvorlik:
  1. PyMuPDF (fitz) — PDF ichidagi matnni to'g'ridan extract qiladi (tez)
  2. Pytesseract  — agar PDF skanerlangan bo'lsa yoki rasm formatida bo'lsa (sekin)

Qo'llab-quvvatlanadigan formatlar: pdf, epub, fb2, txt, doc, docx, djvu
"""

import os
import logging
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Sahifalar soni limiti (juda katta kitoblar uchun)
MAX_PAGES = 50
# Har bir sahifadan olinadigan max belgilar
MAX_CHARS_PER_PAGE = 3000


def extract_text(file_path: str, extension: str) -> str:
    """
    Fayldan matn chiqaradi.
    Qaytaradi: matn satri (bo'sh bo'lishi mumkin)
    """
    ext = extension.lower().strip(".")
    try:
        if ext == "pdf":
            return _extract_pdf(file_path)
        elif ext == "txt":
            return _extract_txt(file_path)
        elif ext in ("doc", "docx"):
            return _extract_docx(file_path)
        elif ext == "fb2":
            return _extract_fb2(file_path)
        elif ext == "epub":
            return _extract_epub(file_path)
        else:
            # Boshqa formatlar uchun PyMuPDF sinab ko'rish
            return _extract_pdf(file_path)
    except Exception as e:
        logger.warning(f"OCR xatosi ({ext}): {e}")
        return ""


def _extract_pdf(file_path: str) -> str:
    """PyMuPDF orqali PDF dan matn olish. Skanerlangan bo'lsa OCR ishlatadi."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF o'rnatilmagan: pip install pymupdf")
        return ""

    texts = []
    try:
        doc = fitz.open(file_path)
        pages = min(len(doc), MAX_PAGES)

        for i in range(pages):
            page = doc[i]
            text = page.get_text("text")

            # Agar sahifada matn kam bo'lsa — skanerlangan, OCR ishlatamiz
            if len(text.strip()) < 50:
                text = _ocr_page(page)

            if text.strip():
                texts.append(text[:MAX_CHARS_PER_PAGE])

        doc.close()
    except Exception as e:
        logger.warning(f"PDF extract xatosi: {e}")

    return "\n\n".join(texts)


def _ocr_page(page) -> str:
    """PyMuPDF sahifasini rasmga aylantirib OCR qiladi."""
    try:
        import pytesseract
        from PIL import Image
        import io

        # Sahifani rasmga render qilish
        mat = page.get_pixmap(dpi=200)
        img_data = mat.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        # Ko'p til: o'zbek lotin + kirill + rus
        # tesseract tillar: uzb (lotin), uzb_cyrl, rus
        langs = "uzb+uzb_cyrl+rus"
        text = pytesseract.image_to_string(img, lang=langs, config="--psm 6")
        return text
    except Exception as e:
        logger.warning(f"OCR (tesseract) xatosi: {e}")
        return ""


def _extract_txt(file_path: str) -> str:
    encodings = ["utf-8", "utf-8-sig", "cp1251", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read(MAX_PAGES * MAX_CHARS_PER_PAGE)
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


def _extract_docx(file_path: str) -> str:
    try:
        import docx
        doc = docx.Document(file_path)
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(parts[:MAX_PAGES * 10])
    except Exception as e:
        logger.warning(f"DOCX extract xatosi: {e}")
        return ""


def _extract_fb2(file_path: str) -> str:
    """FB2 — XML asosidagi format, teglarni tozalaymiz."""
    try:
        import re
        encodings = ["utf-8", "utf-8-sig", "cp1251"]
        raw = ""
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    raw = f.read(MAX_PAGES * MAX_CHARS_PER_PAGE * 2)
                break
            except UnicodeDecodeError:
                continue

        # XML teglarini olib tashlash
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:MAX_PAGES * MAX_CHARS_PER_PAGE]
    except Exception as e:
        logger.warning(f"FB2 extract xatosi: {e}")
        return ""


def _extract_epub(file_path: str) -> str:
    """EPUB — ZIP ichidagi HTML fayllar."""
    try:
        import zipfile
        import re

        texts = []
        with zipfile.ZipFile(file_path, "r") as z:
            html_files = sorted(
                [f for f in z.namelist() if f.endswith((".html", ".xhtml", ".htm"))],
            )
            for fname in html_files[:MAX_PAGES]:
                with z.open(fname) as f:
                    raw = f.read().decode("utf-8", errors="replace")
                text = re.sub(r"<[^>]+>", " ", raw)
                text = re.sub(r"\s+", " ", text).strip()
                if text:
                    texts.append(text[:MAX_CHARS_PER_PAGE])

        return "\n\n".join(texts)
    except Exception as e:
        logger.warning(f"EPUB extract xatosi: {e}")
        return ""
