"""수집기 공용: 사이트 설정 로드, 예의 있는 HTTP 요청, 본문 정제·개인정보 마스킹, 날짜 파싱."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

ALLOWED_DOMAIN = "cnu.ac.kr"  # 계획서 2.4: 학교 도메인 URL만 허용
USER_AGENT = "CampusPickBot/0.1 (CNU student project)"
REQUEST_INTERVAL = 1.0  # 학교 사이트는 빠르게 몰아 요청하면 일시 거부한다(참고: whalecrew2 build-map.js)
SITES_FILE_ENV = "CAMPUS_PICK_SITES_FILE"
DEFAULT_SITES_FILE = Path(__file__).with_name("sites.json")


def load_sites(path: str | os.PathLike | None = None) -> list[dict]:
    """수집 대상 설정. 인자 → 환경변수 CAMPUS_PICK_SITES_FILE → 기본 sites.json 순."""
    p = Path(path or os.environ.get(SITES_FILE_ENV) or DEFAULT_SITES_FILE)
    sites = json.loads(p.read_text(encoding="utf-8"))
    for s in sites:
        for b in s["boards"]:
            if not is_allowed_url(b["url"]):
                raise ValueError(f"학교 도메인이 아닌 수집 대상: {b['url']}")
    return sites


def is_allowed_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return urlparse(url).scheme in ("http", "https") and (host == ALLOWED_DOMAIN or host.endswith("." + ALLOWED_DOMAIN))


class Fetcher:
    """요청 간격 유지 + robots.txt 확인 + 1회 재시도. 사이트별 respect_robots로 robots 확인을 끌 수 있다."""

    def __init__(self, interval: float = REQUEST_INTERVAL, timeout: float = 30.0):
        self.interval = interval
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=False)
        self._last = 0.0
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self.calls = 0

    def _wait(self) -> None:
        gap = time.monotonic() - self._last
        if gap < self.interval:
            time.sleep(self.interval - gap)
        self._last = time.monotonic()

    def robots_allows(self, url: str) -> bool:
        u = urlparse(url)
        root = f"{u.scheme}://{u.netloc}"
        if root not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                self._wait()
                r = self.client.get(root + "/robots.txt")
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])  # robots.txt를 못 읽으면 제한 없음으로 본다(표준 동작)
            self._robots[root] = rp
        return self._robots[root].can_fetch(USER_AGENT, url)

    def get(self, url: str, respect_robots: bool = True) -> str:
        if not is_allowed_url(url):
            raise ValueError(f"학교 도메인이 아닌 URL: {url}")
        if respect_robots and not self.robots_allows(url):
            raise PermissionError(f"robots.txt가 수집을 막음: {url}")
        for attempt in range(2):
            self._wait()
            self.calls += 1
            try:
                r = self.client.get(url)
                if r.status_code in (301, 302, 303, 307, 308):
                    # 로그인 페이지로 돌리는 게시판(예: job.cnu.ac.kr)은 공개 게시판이 아니다
                    raise PermissionError(f"리다이렉트됨(로그인 필요 가능성): {r.headers.get('location')}")
                r.raise_for_status()
                return r.text
            except httpx.HTTPError:
                if attempt:
                    raise
        raise AssertionError("unreachable")

    def close(self) -> None:
        self.client.close()


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# 042-821-7456 · (042)821-7456 · 821-7456 · 1588-1234. '2025-2026' 같은 연도 범위는 제외
PHONE_RE = re.compile(r"(?<!\d)(?:\(?0\d{1,2}[-.)\s]\s?)?(?!(?:19|20)\d\d[-.](?:19|20)\d\d)\d{3,4}[-.]\d{4}(?!\d)")


def mask_pii(text: str) -> str:
    """게시글 속 개인정보(이메일·전화번호)는 저장하지 않는다(계획서 2.4). 원문 링크로 확인하게 한다."""
    return PHONE_RE.sub("[전화번호]", EMAIL_RE.sub("[이메일]", text))


def html_to_text(node) -> str:
    """본문 HTML(문자열 또는 bs4 노드) → 줄 단위 텍스트, 개인정보 마스킹."""
    if node is None:
        return ""
    if isinstance(node, str):
        node = BeautifulSoup(node, "html.parser")
    for br in node.find_all("br"):
        br.replace_with("\n")
    text = node.get_text("\n")
    lines = (re.sub(r"[ \t ​]+", " ", line).strip() for line in text.splitlines())
    return mask_pii("\n".join(line for line in lines if line))


DATE_RE = re.compile(r"(\d{2,4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})")


def parse_date(text: str) -> str | None:
    """'26.11.03' · '2026-11-04' · '2026.11.03 10:00' → 'YYYY-MM-DD'."""
    m = DATE_RE.search(text or "")
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    if y < 100:
        y += 2000
    return f"{y:04d}-{mo:02d}-{d:02d}"


def clean_title(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
