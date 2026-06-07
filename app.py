"""jp_learn — 個人日文學習 App (N4 → N3/N2).

啟動：streamlit run app.py
手機在外面用：搭配 Tailscale 連回家中電腦的 8501 port。
"""
from __future__ import annotations

import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

from corpus import ensure_seeded
from db import get_conn, init_db
from ingest.furigana import annotate_ruby
from ingest.jisho import lookup as jisho_lookup
from ingest.nhk_easy import fetch_latest as nhk_fetch_latest
from srs import get_due_cards, grade_card, init_srs

# ───────────────────────── 啟動初始化 ─────────────────────────
st.set_page_config(
    page_title="jp_learn",
    page_icon="🇯🇵",
    layout="centered",
    initial_sidebar_state="collapsed",
)

init_db()
seed_result = ensure_seeded()
if seed_result is not None:
    total = sum(seed_result.values())
    st.toast(f"首次啟動：匯入 {total} 個 N3 起始單字", icon="✨")


# ───────────────────────── 共用樣式 ─────────────────────────
st.markdown(
    """
    <style>
    /* 大字、行距寬，閱讀文章友善 */
    .jp-article ruby { font-size: 1.35rem; line-height: 2.4; }
    .jp-article rt   { font-size: 0.7rem; color: #888; }
    .jp-word         { font-size: 2.8rem; font-weight: 600; text-align: center; }
    .jp-reading      { font-size: 1.3rem; color: #666; text-align: center; margin-top: -0.5rem; }
    .jp-meaning      { font-size: 1.2rem; text-align: center; margin-top: 1rem; }
    .stat-num        { font-size: 2rem; font-weight: 700; }
    .stat-label      { font-size: 0.85rem; color: #888; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ───────────────────────── 導覽 ─────────────────────────
PAGES = ["📖 複習", "📚 生字本", "📰 文章", "🗞️ NHK 新聞", "📊 進度"]
page = st.sidebar.radio("選單", PAGES, label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption(f"今日：{date.today().isoformat()}")


# ───────────────────────── 工具函式 ─────────────────────────
@st.cache_data(ttl=60)
def stats_summary() -> dict:
    today = date.today().isoformat()
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM vocab").fetchone()["c"]
        due = conn.execute(
            "SELECT COUNT(*) AS c FROM srs WHERE due_date <= ?", (today,)
        ).fetchone()["c"]
        reviewed_today = conn.execute(
            "SELECT COUNT(*) AS c FROM review_log WHERE DATE(reviewed_at) = ?",
            (today,),
        ).fetchone()["c"]
        mastered = conn.execute(
            "SELECT COUNT(*) AS c FROM srs WHERE repetitions >= 5 AND interval_days >= 30"
        ).fetchone()["c"]
    return {
        "total": total,
        "due": due,
        "reviewed_today": reviewed_today,
        "mastered": mastered,
    }


def clear_stats_cache():
    stats_summary.clear()


# ───────────────────────── 📖 複習 ─────────────────────────
def page_review():
    st.title("📖 今日複習")

    s = stats_summary()
    c1, c2, c3 = st.columns(3)
    c1.metric("待複習", s["due"])
    c2.metric("今日已複習", s["reviewed_today"])
    c3.metric("已掌握", s["mastered"])

    with get_conn() as conn:
        due = get_due_cards(conn, limit=30)

    if not due:
        st.success("🎉 今天沒有要複習的字！")
        st.caption("可以去『文章』頁讀點東西，或去『生字本』新增單字。")
        return

    # 卡片進度
    if "review_idx" not in st.session_state:
        st.session_state.review_idx = 0
    if "review_shown" not in st.session_state:
        st.session_state.review_shown = False
    if "review_session_ids" not in st.session_state or set(
        st.session_state.review_session_ids
    ) != {r["id"] for r in due}:
        st.session_state.review_session_ids = [r["id"] for r in due]
        st.session_state.review_idx = 0
        st.session_state.review_shown = False

    idx = st.session_state.review_idx
    total = len(due)
    if idx >= total:
        st.balloons()
        st.success(f"✅ 本輪完成！共複習 {total} 個字")
        if st.button("再來一輪", use_container_width=True):
            st.session_state.review_idx = 0
            st.session_state.review_shown = False
            clear_stats_cache()
            st.rerun()
        return

    card = due[idx]
    st.progress((idx) / total, text=f"{idx + 1} / {total}")

    # 正面：只顯示漢字
    st.markdown(f"<div class='jp-word'>{card['word']}</div>", unsafe_allow_html=True)

    if not st.session_state.review_shown:
        if st.button("顯示答案", type="primary", use_container_width=True):
            st.session_state.review_shown = True
            st.rerun()
    else:
        # 背面：讀音 + 意思 + 詞性
        st.markdown(
            f"<div class='jp-reading'>{card['reading'] or '—'}</div>",
            unsafe_allow_html=True,
        )
        meaning = card["meaning_zh"] or card["meaning_en"] or "（無釋義）"
        st.markdown(f"<div class='jp-meaning'>{meaning}</div>", unsafe_allow_html=True)
        if card["pos"]:
            st.caption(f"詞性：{card['pos']}  ·  JLPT：{card['jlpt_level'] or '—'}")
        if card["note"]:
            st.info(card["note"])

        st.divider()
        st.caption("評估你的記憶程度：")
        cols = st.columns(4)
        # 0 完全忘 / 2 模糊 / 4 想了一下 / 5 秒答
        labels = [
            ("😵 忘記", 0, "secondary"),
            ("😅 模糊", 2, "secondary"),
            ("🤔 想到", 4, "secondary"),
            ("⚡ 秒懂", 5, "primary"),
        ]
        for col, (label, quality, kind) in zip(cols, labels):
            if col.button(label, key=f"q{quality}", type=kind, use_container_width=True):
                with get_conn() as conn:
                    grade_card(conn, card["id"], quality)
                st.session_state.review_idx += 1
                st.session_state.review_shown = False
                clear_stats_cache()
                st.rerun()


# ───────────────────────── 📚 生字本 ─────────────────────────
def page_vocab():
    st.title("📚 生字本")

    with st.expander("➕ 新增單字", expanded=False):
        with st.form("add_vocab", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                word = st.text_input("詞（含漢字）", placeholder="例：勉強")
                reading = st.text_input("假名", placeholder="例：べんきょう")
                jlpt = st.selectbox("JLPT", ["", "N5", "N4", "N3", "N2", "N1"], index=3)
            with col2:
                meaning_zh = st.text_input("中文意思", placeholder="例：學習")
                pos = st.text_input("詞性", placeholder="例：名詞")
                note = st.text_area("筆記（選填）", height=68)

            col_a, col_b = st.columns(2)
            lookup_btn = col_a.form_submit_button("🔍 用 jisho 查", use_container_width=True)
            submit_btn = col_b.form_submit_button("💾 加入生字本", type="primary", use_container_width=True)

            if lookup_btn and word:
                try:
                    results = jisho_lookup(word)
                    if results:
                        r = results[0]
                        st.success(f"jisho 找到：{r.word}（{r.reading}）")
                        st.write("**英文意思：**", "; ".join(r.meanings_en[:5]))
                        st.write("**詞性：**", ", ".join(r.pos[:3]) if r.pos else "—")
                        st.write("**JLPT：**", r.jlpt or "—")
                        st.caption("可手動把資訊複製到上面欄位後加入。")
                    else:
                        st.warning("jisho 沒有找到。")
                except Exception as e:
                    st.error(f"查詢失敗：{e}")

            if submit_btn and word:
                try:
                    with get_conn() as conn:
                        cur = conn.execute(
                            """
                            INSERT INTO vocab (word, reading, meaning_zh, pos, jlpt_level, note, source)
                            VALUES (?, ?, ?, ?, ?, ?, 'manual')
                            """,
                            (word, reading, meaning_zh, pos, jlpt or None, note),
                        )
                        init_srs(conn, cur.lastrowid)
                    clear_stats_cache()
                    st.success(f"✅ 已加入：{word}")
                except sqlite3.IntegrityError:
                    st.warning(f"已存在：{word}（{reading}）")

    st.divider()

    # 篩選
    col1, col2, col3 = st.columns([2, 1, 1])
    keyword = col1.text_input("🔎 搜尋", placeholder="輸入漢字 / 假名 / 中文")
    jlpt_filter = col2.selectbox("JLPT", ["全部", "N5", "N4", "N3", "N2", "N1", "未標"])
    source_filter = col3.selectbox("來源", ["全部", "seed:n3", "manual", "article"])

    sql = "SELECT v.id, v.word, v.reading, v.meaning_zh, v.pos, v.jlpt_level, v.source, s.due_date, s.repetitions FROM vocab v LEFT JOIN srs s ON s.vocab_id = v.id WHERE 1=1"
    params: list = []
    if keyword:
        sql += " AND (v.word LIKE ? OR v.reading LIKE ? OR v.meaning_zh LIKE ?)"
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw])
    if jlpt_filter == "未標":
        sql += " AND v.jlpt_level IS NULL"
    elif jlpt_filter != "全部":
        sql += " AND v.jlpt_level = ?"
        params.append(jlpt_filter)
    if source_filter != "全部":
        if source_filter == "article":
            sql += " AND v.source LIKE 'article%'"
        else:
            sql += " AND v.source = ?"
            params.append(source_filter)
    sql += " ORDER BY v.id DESC LIMIT 200"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    st.caption(f"顯示 {len(rows)} 筆（最多 200）")
    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        df = df.rename(
            columns={
                "word": "詞",
                "reading": "假名",
                "meaning_zh": "中文",
                "pos": "詞性",
                "jlpt_level": "JLPT",
                "source": "來源",
                "due_date": "下次複習",
                "repetitions": "已複習次數",
            }
        )
        st.dataframe(
            df.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("🗑️ 刪除單字"):
            del_word = st.text_input("輸入要刪除的詞（精確比對）")
            if st.button("確認刪除", type="primary") and del_word:
                with get_conn() as conn:
                    cur = conn.execute("DELETE FROM vocab WHERE word = ?", (del_word,))
                clear_stats_cache()
                st.success(f"刪除 {cur.rowcount} 筆")
                st.rerun()


# ───────────────────────── 📰 文章閱讀器 ─────────────────────────
def page_article():
    st.title("📰 文章閱讀器")
    st.caption("貼任何日文 → 自動標假名 → 圈出生字加進生字本")

    if "article_text" not in st.session_state:
        st.session_state.article_text = ""

    text = st.text_area(
        "貼上日文",
        value=st.session_state.article_text,
        height=180,
        placeholder="例：日本では、毎年たくさんの人が花見に行きます。...",
        key="article_input",
    )

    col1, col2 = st.columns(2)
    if col1.button("📖 標假名 + 顯示", type="primary", use_container_width=True):
        st.session_state.article_text = text

    if col2.button("💾 存入文章庫", use_container_width=True):
        if text.strip():
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO article (title, body, source_type) VALUES (?, ?, 'manual')",
                    (text.split("\n", 1)[0][:40], text),
                )
            st.success("已存入文章庫")

    if st.session_state.article_text:
        st.divider()
        st.subheader("📖 標注版本")
        html = annotate_ruby(st.session_state.article_text)
        # 段落保留換行
        html_with_breaks = html.replace("\n", "<br>")
        st.markdown(
            f"<div class='jp-article'>{html_with_breaks}</div>",
            unsafe_allow_html=True,
        )

        st.divider()
        st.subheader("✏️ 加入生字")
        st.caption("從上面文章挑生字，輸入後一鍵查 jisho + 加入")
        new_word = st.text_input("生字（漢字或假名）", key="article_new_word")
        if new_word and st.button("🔍 查詢並加入", type="primary"):
            try:
                results = jisho_lookup(new_word)
                if not results:
                    st.warning("jisho 查不到，請手動到生字本新增")
                else:
                    r = results[0]
                    with get_conn() as conn:
                        try:
                            cur = conn.execute(
                                """
                                INSERT INTO vocab (word, reading, meaning_en, pos, jlpt_level, source)
                                VALUES (?, ?, ?, ?, ?, 'article:reader')
                                """,
                                (
                                    r.word,
                                    r.reading,
                                    "; ".join(r.meanings_en[:3]),
                                    ", ".join(r.pos[:2]),
                                    r.jlpt,
                                ),
                            )
                            init_srs(conn, cur.lastrowid)
                            clear_stats_cache()
                            st.success(f"✅ 已加入：{r.word}（{r.reading}）— {r.meanings_en[0] if r.meanings_en else ''}")
                        except sqlite3.IntegrityError:
                            st.info(f"已存在：{r.word}（{r.reading}）")
            except Exception as e:
                st.error(f"查詢失敗：{e}")


# ───────────────────────── 🗞️ NHK 新聞 ─────────────────────────
def page_nhk():
    st.title("🗞️ NHK News Easy")
    st.caption("N3-N4 等級的真實日語新聞")

    col1, col2 = st.columns([3, 1])
    limit = col1.slider("抓取篇數", 3, 15, 5)
    if col2.button("🔄 抓最新", type="primary", use_container_width=True):
        with st.spinner("抓 NHK 中..."):
            try:
                articles = nhk_fetch_latest(limit=limit)
                with get_conn() as conn:
                    saved = 0
                    for a in articles:
                        cur = conn.execute(
                            """
                            INSERT INTO article (title, body, source_url, source_type, published_at)
                            VALUES (?, ?, ?, 'nhk_easy', ?)
                            """,
                            (a.title, a.body, a.url, a.published_at),
                        )
                        if cur.rowcount > 0:
                            saved += 1
                st.success(f"已抓 {len(articles)} 篇，新增 {saved} 筆")
            except Exception as e:
                st.error(f"抓取失敗：{e}")

    st.divider()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, body, source_url, added_at, read_at
              FROM article
             WHERE source_type = 'nhk_easy'
             ORDER BY added_at DESC
             LIMIT 30
            """
        ).fetchall()

    if not rows:
        st.info("還沒抓過 NHK 新聞，按上面『抓最新』。")
        return

    for r in rows:
        read_mark = "✅ " if r["read_at"] else ""
        with st.expander(f"{read_mark}{r['title']}  ·  {r['added_at'][:10]}"):
            html = annotate_ruby(r["body"])
            st.markdown(
                f"<div class='jp-article'>{html.replace(chr(10), '<br>')}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(f"[原文連結]({r['source_url']})")
            if not r["read_at"]:
                if st.button("📌 標記已讀", key=f"read_{r['id']}"):
                    with get_conn() as conn:
                        conn.execute(
                            "UPDATE article SET read_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (r["id"],),
                        )
                    st.rerun()


# ───────────────────────── 📊 進度儀表板 ─────────────────────────
def page_dashboard():
    st.title("📊 學習進度")

    s = stats_summary()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總單字數", s["total"])
    c2.metric("今日待複習", s["due"])
    c3.metric("今日已複習", s["reviewed_today"])
    c4.metric("已掌握 (≥30天)", s["mastered"])

    st.divider()

    # JLPT 等級分布
    st.subheader("JLPT 等級分布")
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(jlpt_level, '未標') AS level, COUNT(*) AS n
              FROM vocab GROUP BY level ORDER BY level
            """
        ).fetchall()
    if rows:
        df = pd.DataFrame([dict(r) for r in rows]).set_index("level")
        st.bar_chart(df)

    # 過去 30 天複習量
    st.subheader("過去 30 天複習量")
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DATE(reviewed_at) AS d, COUNT(*) AS n
              FROM review_log
             WHERE DATE(reviewed_at) >= DATE('now', '-29 days')
             GROUP BY d ORDER BY d
            """
        ).fetchall()
    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        df["d"] = pd.to_datetime(df["d"])
        full = pd.DataFrame(
            {"d": pd.date_range(end=date.today(), periods=30, freq="D")}
        )
        df = full.merge(df, on="d", how="left").fillna(0).set_index("d")
        st.bar_chart(df)
    else:
        st.info("還沒開始複習。去『複習』頁開始吧。")

    # 即將到期分布（接下來 14 天）
    st.subheader("未來 14 天到期排程")
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT due_date AS d, COUNT(*) AS n
              FROM srs
             WHERE due_date BETWEEN DATE('now') AND DATE('now', '+13 days')
             GROUP BY due_date ORDER BY due_date
            """
        ).fetchall()
    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        df["d"] = pd.to_datetime(df["d"])
        full = pd.DataFrame(
            {"d": pd.date_range(start=date.today(), periods=14, freq="D")}
        )
        df = full.merge(df, on="d", how="left").fillna(0).set_index("d")
        st.bar_chart(df)


# ───────────────────────── 路由 ─────────────────────────
ROUTES = {
    "📖 複習": page_review,
    "📚 生字本": page_vocab,
    "📰 文章": page_article,
    "🗞️ NHK 新聞": page_nhk,
    "📊 進度": page_dashboard,
}
ROUTES[page]()
