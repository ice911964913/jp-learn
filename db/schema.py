"""SQLite schema for jp_learn.

單一檔案 data/jp_learn.db，純本機，無外部依賴。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jp_learn.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS vocab (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    word          TEXT    NOT NULL,           -- 詞（含漢字）
    reading       TEXT,                       -- 假名讀音（ひらがな）
    meaning_zh    TEXT,                       -- 中文意思
    meaning_en    TEXT,                       -- 英文意思（jisho 提供）
    pos           TEXT,                       -- 詞性（名詞 / 動詞 / 形容詞...）
    jlpt_level    TEXT,                       -- N5 / N4 / N3 / N2 / N1
    source        TEXT,                       -- 'seed' / 'article:<id>' / 'manual'
    note          TEXT,                       -- 自己記筆記用
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(word, reading)
);

CREATE INDEX IF NOT EXISTS idx_vocab_jlpt ON vocab(jlpt_level);
CREATE INDEX IF NOT EXISTS idx_vocab_source ON vocab(source);


-- SM-2 排程：每個 vocab 一筆
CREATE TABLE IF NOT EXISTS srs (
    vocab_id      INTEGER PRIMARY KEY,
    ef            REAL    NOT NULL DEFAULT 2.5,   -- easiness factor
    interval_days INTEGER NOT NULL DEFAULT 0,
    repetitions   INTEGER NOT NULL DEFAULT 0,
    due_date      TEXT    NOT NULL,                -- YYYY-MM-DD
    last_reviewed TEXT,
    FOREIGN KEY (vocab_id) REFERENCES vocab(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_srs_due ON srs(due_date);


-- 每次複習歷史紀錄
CREATE TABLE IF NOT EXISTS review_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    vocab_id      INTEGER NOT NULL,
    quality       INTEGER NOT NULL,           -- 0-5 SM-2 評分
    reviewed_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vocab_id) REFERENCES vocab(id) ON DELETE CASCADE
);


-- 文章：貼上去或從 NHK 抓的
CREATE TABLE IF NOT EXISTS article (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT,
    body          TEXT    NOT NULL,
    source_url    TEXT,
    source_type   TEXT,                       -- 'nhk_easy' / 'manual' / 'asahi' ...
    published_at  TEXT,                       -- 原文發布日（如有）
    added_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at       TEXT                        -- 標記已讀的時間
);

CREATE INDEX IF NOT EXISTS idx_article_added ON article(added_at DESC);


-- 文法句型筆記（之後可擴充）
CREATE TABLE IF NOT EXISTS grammar (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern       TEXT    NOT NULL,           -- 〜にとって
    jlpt_level    TEXT,
    meaning_zh    TEXT,
    example_jp    TEXT,
    example_zh    TEXT,
    note          TEXT,
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pattern)
);


-- 中文釋義快取（Claude 依 jisho 英文釋義寫的繁中意思，每字只查一次）
CREATE TABLE IF NOT EXISTS zh_gloss (
    word          TEXT    NOT NULL,
    reading       TEXT    NOT NULL,
    meaning_zh    TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (word, reading)
);


-- key-value 設定（首次啟動標記、版本等）
CREATE TABLE IF NOT EXISTS settings (
    key           TEXT    PRIMARY KEY,
    value         TEXT
);
"""


def get_conn(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """取得 SQLite 連線（自動建立 data/ 目錄）。"""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path | str = DB_PATH) -> None:
    """建表（idempotent，重複呼叫安全）。"""
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {DB_PATH}")
