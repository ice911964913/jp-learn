"""MATCHA やさしい日本語 RSS 抓取.

NHK News Easy 2026 改版後需登入 NHK ONE 才能取得文章清單，改用 MATCHA 簡單日語版。
MATCHA 是 N4-N3 程度的旅遊/文化文章，RSS 內含完整內文，不用逐篇爬。
URL: https://matcha-jp.com/easy/
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Optional
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

MATCHA_FEED = "https://matcha-jp.com/easy/feed"
USER_AGENT = "Mozilla/5.0 (jp_learn personal-use scraper)"
DEFAULT_TIMEOUT = 20
_CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"
_BLOCK_TAGS = ["h2", "h3", "h4", "p", "li"]


@dataclass
class EasyArticle:
    title: str
    body: str
    url: str
    published_at: Optional[str]


def _plain_text(markup: str) -> str:
    """去掉 <rt>/<rp>（讀音、英文註解），保留漢字本體 → 我們自己標假名。"""
    soup = BeautifulSoup(markup, "lxml")
    for tag in soup.find_all(["rt", "rp", "figure", "figcaption", "script", "style"]):
        tag.decompose()
    lines = []
    for block in soup.find_all(_BLOCK_TAGS):
        # 巢狀 block（如 li 內的 p）只取最外層，避免重複
        if block.find_parent(_BLOCK_TAGS):
            continue
        text = block.get_text("", strip=True)
        if text:
            lines.append(text)
    return "\n".join(lines)


def fetch_latest(limit: int = 5) -> list[EasyArticle]:
    """抓 RSS 最新 N 篇（含內文）。"""
    resp = requests.get(MATCHA_FEED, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    out: list[EasyArticle] = []
    for item in root.iterfind("channel/item"):
        body = _plain_text(item.findtext(_CONTENT_NS) or "")
        if not body:
            continue
        pub = item.findtext("pubDate")
        out.append(
            EasyArticle(
                # 標題的 ruby 被跳脫兩次，要先還原
                title=_plain_text(f"<p>{html.unescape(item.findtext('title') or '')}</p>"),
                body=body,
                url=item.findtext("link") or "",
                published_at=parsedate_to_datetime(pub).date().isoformat() if pub else None,
            )
        )
        if len(out) >= limit:
            break
    return out
