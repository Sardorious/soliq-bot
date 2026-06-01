import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = os.getenv("DB_PATH", "books.db")


class Storage:
    def __init__(self):
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    title       TEXT    NOT NULL,
                    file_id     TEXT    NOT NULL,
                    file_name   TEXT,
                    extension   TEXT,
                    size        INTEGER DEFAULT 0,
                    date        TEXT    NOT NULL,
                    -- OCR + tahlil
                    raw_text    TEXT    DEFAULT '',
                    keywords    TEXT    DEFAULT '[]',
                    topics      TEXT    DEFAULT '[]',
                    summary     TEXT    DEFAULT '',
                    language    TEXT    DEFAULT '',
                    analyzed    INTEGER DEFAULT 0
                )
            """)
            # Migratsiya: eski jadvalga yangi ustunlar qo'shish
            existing = {row[1] for row in conn.execute("PRAGMA table_info(books)")}
            new_cols = {
                "raw_text":  "TEXT DEFAULT ''",
                "keywords":  "TEXT DEFAULT '[]'",
                "topics":    "TEXT DEFAULT '[]'",
                "summary":   "TEXT DEFAULT ''",
                "language":  "TEXT DEFAULT ''",
                "analyzed":  "INTEGER DEFAULT 0",
            }
            for col, definition in new_cols.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE books ADD COLUMN {col} {definition}")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_user ON books(user_id)")
            conn.commit()

    # ── WRITE ──────────────────────────────────

    def add_book(
        self,
        user_id: int,
        title: str,
        file_id: str,
        extension: str = "",
        size: int = 0,
        file_name: str = "",
    ) -> int:
        date = datetime.now().strftime("%d.%m.%Y %H:%M")
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO books (user_id, title, file_id, file_name, extension, size, date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, title, file_id, file_name, extension.lower(), size, date),
            )
            conn.commit()
            return cur.lastrowid

    def save_analysis(self, book_id: int, analysis: Dict):
        """OCR + tahlil natijasini saqlash."""
        with self._connect() as conn:
            conn.execute(
                """UPDATE books
                   SET raw_text = ?, keywords = ?, topics = ?,
                       summary = ?, language = ?, analyzed = 1
                   WHERE id = ?""",
                (
                    analysis.get("raw_text", "")[:50000],
                    json.dumps(analysis.get("keywords", []), ensure_ascii=False),
                    json.dumps(analysis.get("topics", []), ensure_ascii=False),
                    analysis.get("summary", ""),
                    analysis.get("language", ""),
                    book_id,
                ),
            )
            conn.commit()

    def delete_book(self, user_id: int, book_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM books WHERE id = ? AND user_id = ?", (book_id, user_id)
            )
            conn.commit()
            return cur.rowcount > 0

    # ── READ ───────────────────────────────────

    def get_books(self, user_id: int) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM books WHERE user_id = ? ORDER BY id DESC", (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_books_for_linking(self, user_id: int, exclude_id: int) -> List[Dict]:
        """Bog'liqlik hisoblash uchun — raw_text bilan, faqat tahlil qilinganlar."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, title, keywords, topics, raw_text
                   FROM books
                   WHERE user_id = ? AND id != ? AND analyzed = 1""",
                (user_id, exclude_id),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_book(self, user_id: int, book_id: int) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE id = ? AND user_id = ?", (book_id, user_id)
            ).fetchone()
            return dict(row) if row else None

    def search_books(self, user_id: int, query: str) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM books
                   WHERE user_id = ?
                     AND (title LIKE ? OR file_name LIKE ? OR keywords LIKE ?)
                   ORDER BY id DESC""",
                (user_id, f"%{query}%", f"%{query}%", f"%{query}%"),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_book_count(self, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM books WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row["cnt"] if row else 0

    def get_stats(self, user_id: int) -> Dict:
        with self._connect() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) as cnt, COALESCE(SUM(size),0) as total_size FROM books WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            ext_rows = conn.execute(
                """SELECT extension, COUNT(*) as cnt
                   FROM books WHERE user_id = ?
                   GROUP BY extension ORDER BY cnt DESC""",
                (user_id,),
            ).fetchall()
        by_ext = {r["extension"] or "?": r["cnt"] for r in ext_rows}
        return {
            "total": total_row["cnt"],
            "total_size": total_row["total_size"],
            "by_ext": by_ext,
        }
