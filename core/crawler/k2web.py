"""학과 홈페이지(K2Web CMS, *.cnu.ac.kr/.../*.do) 게시판 파서. computer·biz 등 학과 사이트가 같은 틀을 쓴다.

목록: table.board-table tbody tr (tr.b-top-box = 상단 고정 공지), 제목 링크 ?mode=view&articleNo=N
본문: .fr-view, 첨부: a[href*=mode=download]
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from .common import clean_title, html_to_text, is_allowed_url, parse_date

PAGE_SIZE = 10


def list_url(board_url: str, page: int) -> str:
    return f"{board_url}?mode=list&articleLimit={PAGE_SIZE}&article.offset={(page - 1) * PAGE_SIZE}"


def view_url(board_url: str, article_no: str) -> str:
    return f"{board_url}?mode=view&articleNo={article_no}"


def parse_list(html: str, board_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("table.board-table tbody tr"):
        a = tr.select_one(".b-title-box a[href*='articleNo=']")
        if not a:
            continue  # '등록된 글이 없습니다' 같은 행
        no = parse_qs(urlparse(a["href"]).query).get("articleNo", [None])[0]
        date = tr.select_one(".b-date")
        rows.append({
            "article_no": no,
            "title": clean_title(a.get_text()),
            "url": view_url(board_url, no),
            "posted_at": parse_date(date.get_text() if date else ""),
            "pinned": "b-top-box" in (tr.get("class") or []),
        })
    return rows


def parse_view(html: str, page_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".fr-view") or soup.select_one(".b-content-box")
    attachments = []
    for a in soup.select("a[href*='mode=download']"):
        url = urljoin(page_url, a["href"])
        name = re.sub(r"^\d+\.\s*", "", clean_title(a.get_text()))
        if is_allowed_url(url) and name and all(x["url"] != url for x in attachments):
            attachments.append({"name": name, "url": url})
    return {"content": html_to_text(body), "attachments": attachments}
