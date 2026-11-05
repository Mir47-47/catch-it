"""수집 실행: sites.json의 게시판을 HTML 또는 공식 API로 모아 사이트별 JSON으로 저장하고, 두 방식 결과를 비교한다.

출력: {data_dir}/{method}/{site}.json, {data_dir}/{method}/_report.json   (method = html | api)

    python -m crawler.collect --method html --limit 10
    CNU_KEY=... python -m crawler.collect --method api
    python -m crawler.collect --compare
    CNU_KEY=... python -m crawler.collect --list-api-boards
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from datetime import datetime
from pathlib import Path

import httpx

from . import cnu_api, k2web, plus
from .common import Fetcher, load_sites

log = logging.getLogger("crawler")
PARSERS = {"k2web": k2web, "plus": plus}
METHODS = ("html", "api")
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
API_LATEST = 50  # API는 게시판 글을 한꺼번에 준다. 최신 N건만 저장(whalecrew2와 같은 값)


def _now() -> str:
    return datetime.now(cnu_api.KST).isoformat(timespec="seconds")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def make_post(site: dict, board: dict, row: dict, method: str, collected_at: str) -> dict:
    return {
        "id": f"{site['site']}:{board['board']}:{row['article_no']}",
        "site": site["site"], "site_name": site["name"],
        "board": board["board"], "board_name": board["name"],
        **row,
        "method": method,
        "collected_at": collected_at,
    }


def dedupe(posts: list[dict]) -> list[dict]:
    """같은 공지를 여러 게시판에 올린 경우(제목·게시일 같음) 앞의 것만 남기고 also_in에 게시판을 적는다."""
    by_key: dict[tuple, dict] = {}
    for p in posts:
        k = (p["title"], p["posted_at"])
        first = by_key.get(k)
        if first is None:
            by_key[k] = p
        elif first["id"] != p["id"]:
            first.setdefault("also_in", []).append(p["board"])
    return list(by_key.values())


def crawl_board_html(fetcher: Fetcher, site: dict, board: dict, limit: int,
                     prev_by_id: dict, fetch_body: bool = True) -> list[dict]:
    """목록을 limit건(고정 공지 제외)이 찰 때까지 넘기고, 새 글만 본문을 받는다."""
    parser = PARSERS[site["parser"]]
    respect = site.get("respect_robots", True)
    fetch_body = fetch_body and board.get("fetch_body", True)  # 본문이 로그인 필요한 게시판은 목록만
    rows: dict[str, dict] = {}
    normal = 0
    for page in range(1, math.ceil(limit / 10) + 2):
        got = [r for r in parser.parse_list(fetcher.get(parser.list_url(board["url"], page), respect), board["url"])
               if r["article_no"] not in rows]
        if not got:
            break
        for r in got:
            rows[r["article_no"]] = r
            normal += not r["pinned"]
        if normal >= limit:
            break
    pinned = [r for r in rows.values() if r["pinned"]]
    latest = [r for r in rows.values() if not r["pinned"]][:limit]

    now = _now()
    posts = []
    for r in pinned + latest:
        post = make_post(site, board, r, "html", now)
        # 다른 게시판 중복으로 저장되지 않은 글도 제목·게시일로 찾아 본문을 재사용한다
        prev = prev_by_id.get(post["id"]) or prev_by_id.get((r["title"], r["posted_at"]))
        if prev and prev.get("title") == r["title"] and prev.get("content") is not None:
            post.update(content=prev["content"], attachments=prev.get("attachments", []),
                        collected_at=prev.get("collected_at", now))  # 이미 받은 글은 다시 요청하지 않는다
        elif fetch_body:
            try:
                post.update(parser.parse_view(fetcher.get(r["url"], respect), r["url"]))
            except (PermissionError, httpx.HTTPError) as e:
                # 회원 전용 글(로그인으로 리다이렉트) 등: 글 하나 때문에 게시판 전체를 실패시키지 않는다. 다음 수집 때 재시도
                post.update(content=None, attachments=[], content_error=f"{type(e).__name__}: {e}")
        else:
            post.update(content=None, attachments=[])
        posts.append(post)
    return posts


def crawl_board_api(client: httpx.Client, key: str, site: dict, board: dict) -> list[dict]:
    if board.get("api_board_no") is None:
        raise LookupError("api_board_no 미지정(sites.json) — list_api_boards()로 번호를 찾아 넣는다")
    view_url = PARSERS[site["parser"]].view_url
    rows = cnu_api.to_rows(cnu_api.fetch_board(client, key, board["api_board_no"]), board["url"], view_url)
    now = _now()
    return [make_post(site, board, r, "api", now) for r in rows[:API_LATEST]]


def collect(method: str = "html", sites: list[str] | None = None, limit: int = 10,
            data_dir: str | Path | None = None, fetch_body: bool = True, sites_file=None) -> dict:
    """수집 후 사이트별 JSON과 _report.json을 쓰고 리포트를 돌려준다. 실패한 게시판은 지난 수집분을 유지한다."""
    if method not in METHODS:
        raise ValueError(f"method는 {METHODS} 중 하나")
    out_dir = Path(data_dir or DEFAULT_DATA_DIR) / method
    out_dir.mkdir(parents=True, exist_ok=True)
    targets = [s for s in load_sites(sites_file) if not sites or s["site"] in sites]

    key = None
    if method == "api":
        key = cnu_api.get_key()
        if not key:
            raise RuntimeError(f"{cnu_api.KEY_ENV} 환경변수가 없습니다(공식 API 발급키)")
    fetcher = Fetcher() if method == "html" else None
    client = httpx.Client(timeout=30) if method == "api" else None

    report = {"method": method, "at": _now(), "sites": {}}
    try:
        for site in targets:
            file = out_dir / f"{site['site']}.json"
            prev_posts = (_read_json(file) or {}).get("posts", [])
            prev_by_id = {p["id"]: p for p in prev_posts}
            prev_by_id.update({(p["title"], p["posted_at"]): p for p in prev_posts})
            posts, boards_report, ok = [], {}, True
            for board in site["boards"]:
                try:
                    if method == "html":
                        got = crawl_board_html(fetcher, site, board, limit, prev_by_id, fetch_body)
                    else:
                        got = crawl_board_api(client, key, site, board)
                    new = sum(p["id"] not in prev_by_id for p in got)
                    boards_report[board["board"]] = {"count": len(got), "new": new}
                    if not got:
                        # 계획서 1.2 안정성: 0건이면 사이트 구조 변경 등을 의심한다
                        log.warning("%s/%s: 0건 — 사이트 구조 변경 가능성", site["site"], board["board"])
                    posts.extend(got)
                except LookupError as e:
                    boards_report[board["board"]] = {"skipped": str(e)}
                except Exception as e:  # noqa: BLE001 — 한 게시판 실패가 전체 수집을 멈추지 않게
                    ok = False
                    log.error("%s/%s 수집 실패: %s", site["site"], board["board"], e)
                    kept = [{k: v for k, v in p.items() if k != "also_in"}
                            for p in prev_posts if p["board"] == board["board"]]
                    boards_report[board["board"]] = {"error": f"{type(e).__name__}: {e}", "kept_previous": len(kept)}
                    posts.extend(kept)
                log.info("%s/%s: %s", site["site"], board["board"], boards_report[board["board"]])
            posts = dedupe(posts)
            file.write_text(json.dumps({"site": site["site"], "name": site["name"], "method": method,
                                        "updated": _now(), "ok": ok, "posts": posts},
                                       ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            report["sites"][site["site"]] = {"ok": ok, "posts": len(posts), "boards": boards_report}
    finally:
        if fetcher:
            report["requests"] = fetcher.calls
            fetcher.close()
        if client:
            client.close()
    (out_dir / "_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return report


def load_posts(method: str, data_dir: str | Path | None = None) -> list[dict]:
    out_dir = Path(data_dir or DEFAULT_DATA_DIR) / method
    posts = []
    for f in sorted(out_dir.glob("[!_]*.json")):
        posts.extend((_read_json(f) or {}).get("posts", []))
    return posts


def compare(data_dir: str | Path | None = None) -> list[dict]:
    """HTML vs API 결과를 게시판별로 비교. API 쪽은 HTML이 본 기간(고정 공지 제외 최소 게시일 이후)만 센다."""
    html = load_posts("html", data_dir)
    api = load_posts("api", data_dir)
    out = []
    for key in sorted({(p["site"], p["board"]) for p in html + api}):
        h = {p["id"]: p for p in html if (p["site"], p["board"]) == key}
        a = {p["id"]: p for p in api if (p["site"], p["board"]) == key}
        dates = [p["posted_at"] for p in h.values() if not p.get("pinned") and p.get("posted_at")]
        since = min(dates) if dates else None
        a_window = {i for i, p in a.items() if since and (p.get("posted_at") or "") >= since}
        both = h.keys() & a.keys()
        out.append({
            "site": key[0], "board": key[1], "html": len(h), "api": len(a), "both": len(both),
            "html_only": sorted(h.keys() - a.keys()),
            "api_only_in_window": sorted(a_window - h.keys()),
            "title_diff": sorted(i for i in both if h[i]["title"] != a[i]["title"]),
            "content_empty_html": sum(not (h[i].get("content") or "") for i in both),
            "content_empty_api": sum(not (a[i].get("content") or "") for i in both),
        })
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="교내 게시판 수집")
    ap.add_argument("--method", choices=METHODS, default="html")
    ap.add_argument("--limit", type=int, default=10, help="게시판별 최신 글 수(고정 공지 제외, HTML만)")
    ap.add_argument("--sites", help="쉼표 구분 site id (기본: 전체)")
    ap.add_argument("--no-body", action="store_true", help="본문은 받지 않음(HTML)")
    ap.add_argument("--data-dir")
    ap.add_argument("--compare", action="store_true", help="수집 없이 html/api 결과 비교")
    ap.add_argument("--list-api-boards", action="store_true", help="공식 API 게시판 목록 출력(CNU_KEY 필요)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # 요청마다 찍히는 로그 숨김

    if args.list_api_boards:
        for b in cnu_api.list_boards():
            print(f"{b['board_no']}\t{b['site_nm']}\t{b['board_nm']}")
        return
    if args.compare:
        print(json.dumps(compare(args.data_dir), ensure_ascii=False, indent=1))
        return
    report = collect(args.method, args.sites.split(",") if args.sites else None, args.limit,
                     args.data_dir, not args.no_body)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if not any(s["posts"] for s in report["sites"].values()):
        raise SystemExit(1)  # 전부 0건 = 차단·구조 변경. 배치에서 실패로 감지되게


if __name__ == "__main__":
    main()
