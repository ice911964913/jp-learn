"""SM-2 spaced repetition algorithm.

評分尺度 (quality)：
  0  完全不記得（不算錯誤 + 重置）
  1  錯誤但有印象
  2  錯誤但答案出來時很熟悉
  3  正確但需要思考很久（吃力）
  4  正確，些微遲疑
  5  完全正確、瞬間反應

quality < 3 視為失敗：重複次數重置、interval 重置到 1 天。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class SrsState:
    ef: float
    interval_days: int
    repetitions: int
    due_date: date


def _next_state(prev: SrsState, quality: int) -> SrsState:
    if not 0 <= quality <= 5:
        raise ValueError("quality must be 0..5")

    if quality < 3:
        repetitions = 0
        interval = 1
    else:
        if prev.repetitions == 0:
            interval = 1
        elif prev.repetitions == 1:
            interval = 6
        else:
            interval = round(prev.interval_days * prev.ef)
        repetitions = prev.repetitions + 1

    ef = prev.ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ef = max(1.3, ef)

    return SrsState(
        ef=ef,
        interval_days=interval,
        repetitions=repetitions,
        due_date=date.today() + timedelta(days=interval),
    )


def init_srs(conn: sqlite3.Connection, vocab_id: int) -> None:
    """為新單字建立 SRS 排程（首日就到期）。"""
    conn.execute(
        """
        INSERT OR IGNORE INTO srs (vocab_id, ef, interval_days, repetitions, due_date)
        VALUES (?, 2.5, 0, 0, ?)
        """,
        (vocab_id, date.today().isoformat()),
    )
    conn.commit()


def grade_card(conn: sqlite3.Connection, vocab_id: int, quality: int) -> SrsState:
    """更新該單字的 SRS 狀態並寫入 review_log。回傳新狀態。"""
    row = conn.execute(
        "SELECT ef, interval_days, repetitions, due_date FROM srs WHERE vocab_id = ?",
        (vocab_id,),
    ).fetchone()
    if row is None:
        init_srs(conn, vocab_id)
        row = conn.execute(
            "SELECT ef, interval_days, repetitions, due_date FROM srs WHERE vocab_id = ?",
            (vocab_id,),
        ).fetchone()

    prev = SrsState(
        ef=row["ef"],
        interval_days=row["interval_days"],
        repetitions=row["repetitions"],
        due_date=date.fromisoformat(row["due_date"]),
    )
    nxt = _next_state(prev, quality)

    conn.execute(
        """
        UPDATE srs
           SET ef = ?, interval_days = ?, repetitions = ?,
               due_date = ?, last_reviewed = CURRENT_TIMESTAMP
         WHERE vocab_id = ?
        """,
        (nxt.ef, nxt.interval_days, nxt.repetitions, nxt.due_date.isoformat(), vocab_id),
    )
    conn.execute(
        "INSERT INTO review_log (vocab_id, quality) VALUES (?, ?)",
        (vocab_id, quality),
    )
    conn.commit()
    return nxt


def get_due_cards(
    conn: sqlite3.Connection,
    limit: int = 50,
    include_new: bool = True,
) -> list[sqlite3.Row]:
    """取得今日該複習的單字（已到期 + 從未複習過的新卡）。"""
    today = date.today().isoformat()
    query = """
        SELECT v.id, v.word, v.reading, v.meaning_zh, v.meaning_en,
               v.pos, v.jlpt_level, v.note,
               s.ef, s.interval_days, s.repetitions, s.due_date, s.last_reviewed
          FROM vocab v
          JOIN srs s ON s.vocab_id = v.id
         WHERE s.due_date <= ?
    """
    if not include_new:
        query += " AND s.repetitions > 0"
    query += " ORDER BY s.due_date ASC, v.id ASC LIMIT ?"

    return conn.execute(query, (today, limit)).fetchall()


def schedule_next(prev_ef: float, prev_interval: int, prev_reps: int, quality: int) -> SrsState:
    """純函式版本，方便測試 / 預覽下次到期日。"""
    return _next_state(
        SrsState(ef=prev_ef, interval_days=prev_interval, repetitions=prev_reps, due_date=date.today()),
        quality,
    )
