"""충남대 본부 홈페이지(plus.cnu.ac.kr/_prog/_board) 게시판 파서.

목록: table tbody tr (td.num이 '공지'면 고정 공지), 제목 링크 ./?mode=V&no=N&code=...
본문: .board_viewDetail (PDF 뷰어만 있는 글은 본문이 비고 첨부로 남는다), 첨부: ul.board_viewInfo li.file a
"""
from __future__ import annotations

from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from .common import clean_title, html_to_text, is_allowed_url, parse_date


def list_url(board_url: str, page: int) -> str:
    return f"{board_url}&GotoPage={page}"


def view_url(board_url: str, article_no: str) -> str:
    return f"{board_url}&mode=V&no={article_no}"


def parse_list(html: str, board_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr"):
        a = tr.select_one("td.title a[href*='no=']")
        if not a:
            continue
        no = parse_qs(urlparse(a["href"]).query).get("no", [None])[0]
        num = tr.select_one("td.num")
        date = tr.select_one("td.date")
        rows.append({
            "article_no": no,
            "title": clean_title(a.get_text()),
            "url": view_url(board_url, no),
            "posted_at": parse_date(date.get_text() if date else ""),
            "pinned": bool(num and num.get_text(strip=True) == "공지"),
        })
    return rows


def parse_view(html: str, page_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    parts = [html_to_text(d) for d in soup.select(".board_viewDetail")]
    attachments = []
    for a in soup.select("ul.board_viewInfo li.file a[href]"):
        url = urljoin(page_url, a["href"])
        name = clean_title(a.get("title") or a.get_text())
        if is_allowed_url(url) and name and all(x["url"] != url for x in attachments):
            attachments.append({"name": name, "url": url})
    return {"content": "\n".join(p for p in parts if p), "attachments": attachments}
