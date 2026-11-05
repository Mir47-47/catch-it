"""학교 공식 게시판 API(api.cnu.ac.kr) 수집. 발급키 CNU_KEY가 있어야 동작한다.

호출 방식은 whalecrew2 collector/collect.js를 따른다:
- 키가 URL·로그에 남지 않도록 POST form(AUTH_KEY, P_board_no)만 쓴다(학교 요구사항).
- 응답 {"RESULT": [{article_no, article_title, article_text, attach_cnt, update_dt: {time}}...]}
- 게시판 번호 목록은 cmsBoard API로 조회한다(본부 게시판 번호 찾기용).
API는 상단 고정 여부·첨부파일 이름을 주지 않고, 게시일 대신 수정일(update_dt)만 준다.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx

from .common import clean_title, html_to_text

CONTENTS_API = "https://api.cnu.ac.kr/svc/offcam/pub/homepageboardContents"
BOARD_LIST_API = "https://api.cnu.ac.kr/svc/offcam/pub/cmsBoard"
KEY_ENV = "CNU_KEY"
KST = timezone(timedelta(hours=9))


def get_key() -> str | None:
    return (os.environ.get(KEY_ENV) or "").strip() or None


def _post(client: httpx.Client, url: str, params: dict) -> dict:
    r = client.post(url, data=params)
    r.raise_for_status()
    j = r.json()
    if not isinstance(j.get("RESULT"), list):
        # 키 만료·잘못된 게시판 번호 등. 응답 일부만 남기고 키는 넣지 않는다
        raise RuntimeError(f"API 오류 응답: {str(j.get('OutBlock') or j)[:120]}")
    return j


def fetch_board(client: httpx.Client, key: str, board_no: int) -> list[dict]:
    return _post(client, CONTENTS_API, {"AUTH_KEY": key, "P_board_no": str(board_no)})["RESULT"]


def list_boards(key: str | None = None) -> list[dict]:
    """API로 받을 수 있는 게시판 목록 [{board_no, board_nm, site_nm}, ...]."""
    key = key or get_key()
    if not key:
        raise RuntimeError(f"{KEY_ENV} 환경변수가 없습니다")
    with httpx.Client(timeout=30) as c:
        rows = _post(c, BOARD_LIST_API, {"AUTH_KEY": key})["RESULT"]
    return [{"board_no": int(b["board_no"]), "board_nm": str(b.get("board_nm", "")).strip(),
             "site_nm": str(b.get("site_nm", "")).strip()} for b in rows]


def _date(row: dict) -> str | None:
    t = (row.get("update_dt") or {}).get("time")  # update_dt가 빠진 글도 있다
    return datetime.fromtimestamp(t / 1000, KST).strftime("%Y-%m-%d") if t else None


def to_rows(api_rows: list[dict], board_url: str, view_url) -> list[dict]:
    """API 응답 → HTML 파서와 같은 모양의 행(목록+본문). 최신 글 먼저."""
    out = []
    for x in sorted(api_rows, key=lambda r: (r.get("update_dt") or {}).get("time") or 0, reverse=True):
        no = str(x["article_no"])
        out.append({
            "article_no": no,
            "title": clean_title(x.get("article_title")),
            "url": view_url(board_url, no),
            "posted_at": _date(x),
            "pinned": None,  # API는 고정 여부를 주지 않는다
            "content": html_to_text(x.get("article_text") or ""),
            "attachments": [],  # 이름·주소 없이 개수만 준다
            "attach_count": int(x.get("attach_cnt") or 0),
        })
    return out
