"""NHK News Web Easy 爬蟲.

NHK Easy 是公認 N3-N4 程度的真實新聞，自帶假名標注。
URL: https://www3.nhk.or.jp/news/easy/

注意：NHK 偶爾改版/下架，建議搭配 fallback。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

NHK_BASE = "https://www3.nhk.or.jp/news/easy"
NHK_LIST_JSON = f"{NHK_BASE}/news-list.json"
USER_AGENT = "Mozilla/5.0 (jp_learn personal-use scraper)"
DEFAULT_TIMEOUT = 10


@dataclass
class NhkArticle:
    news_id: str
    title: str
    body: str
    url: str
    published_at: Optional[str]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def list_recent(limit: int = 10) -> list[dict]:
    """抓最新文章清單（不含內文）。回傳 dict 列表，每筆有 news_id / title / date。"""
    s = _session()
    resp = s.get(NHK_LIST_JSON, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()

    out: list[dict] = []
    if not payload:
        return out

    # 結構：[ { "YYYY-MM-DD": [ {news_id, title, ...}, ...] }, ... ]
    first_bucket = payload[0]
    for date_key, items in first_bucket.items():
        for item in items:
            out.append(
                {
                    "news_id": item.get("news_id"),
                    "title": item.get("title"),
                    "date": item.get("news_prearranged_time") or date_key,
                }
            )
            if len(out) >= limit:
                return out
    return out


def fetch_article(news_id: str) -> NhkArticle:
    """抓單篇文章內文。"""
    url = f"{NHK_BASE}/{news_id}/{news_id}.html"
    s = _session()
    resp = s.get(url, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "lxml")

    title_tag = soup.find("h1", class_=re.compile("title", re.I)) or soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # 主文容器：NHK Easy 用 #js-article-body 或 .article-main__body
    body_tag = (
        soup.find(id="js-article-body")
        or soup.find("div", class_=re.compile("article-main__body|article-body", re.I))
        or soup.find("article")
    )
    if body_tag:
        # 移除 ruby 內的 <rt>（讀音），保留漢字本體 → 我們自己標假名
        for rt in body_tag.find_all("rt"):
            rt.decompose()
        for rp in body_tag.find_all("rp"):
            rp.decompose()
        body = body_tag.get_text("\n", strip=True)
    else:
        body = ""

    return NhkArticle(
        news_id=news_id,
        title=title,
        body=body,
        url=url,
        published_at=datetime.now().isoformat(timespec="seconds"),
    )


def fetch_latest(limit: int = 5) -> list[NhkArticle]:
    """抓最新 N 篇文章（含內文）。"""
    items = list_recent(limit=limit)
    out: list[NhkArticle] = []
    for it in items:
        nid = it.get("news_id")
        if not nid:
            continue
        try:
            out.append(fetch_article(nid))
        except Exception as e:
            print(f"[nhk] failed {nid}: {e}")
    return out
