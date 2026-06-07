"""把 corpus/*.csv 匯入 SQLite vocab + 建立 SRS 排程.

執行：python -m corpus.seed
首次啟動 App 時也會自動跑。
"""
from __future__ import annotations

import csv
from pathlib import Path

from db import get_conn, init_db
from srs import init_srs

CORPUS_DIR = Path(__file__).resolve().parent

SEED_FILES = [
    ("n3_starter.csv", "seed:n3"),
]


def seed_all() -> dict[str, int]:
    """匯入所有 seed 檔案。回傳 {file: imported_count}。已存在的字會跳過。"""
    init_db()
    stats: dict[str, int] = {}

    with get_conn() as conn:
        for filename, source_tag in SEED_FILES:
            path = CORPUS_DIR / filename
            if not path.exists():
                stats[filename] = 0
                continue

            imported = 0
            with path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cur = conn.execute(
                        """
                        INSERT OR IGNORE INTO vocab
                            (word, reading, meaning_zh, pos, jlpt_level, source)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["word"].strip(),
                            row.get("reading", "").strip(),
                            row.get("meaning_zh", "").strip(),
                            row.get("pos", "").strip(),
                            row.get("jlpt_level", "").strip(),
                            source_tag,
                        ),
                    )
                    if cur.rowcount > 0:
                        vocab_id = cur.lastrowid
                        init_srs(conn, vocab_id)
                        imported += 1
                conn.commit()
            stats[filename] = imported

    return stats


def is_seeded() -> bool:
    """判斷 DB 是否已經 seed 過（避免重複跑）。"""
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'seeded'").fetchone()
        return row is not None and row["value"] == "1"


def mark_seeded() -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('seeded', '1')"
        )
        conn.commit()


def ensure_seeded() -> dict[str, int] | None:
    """便利函式：App 啟動時呼叫。已 seed 過則回傳 None。"""
    if is_seeded():
        return None
    stats = seed_all()
    mark_seeded()
    return stats


if __name__ == "__main__":
    stats = seed_all()
    mark_seeded()
    for f, n in stats.items():
        print(f"  {f}: {n} new words imported")
