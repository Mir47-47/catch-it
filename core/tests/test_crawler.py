"""수집기 단위 테스트. 네트워크 없이 실제 사이트 구조를 본뜬 합성 HTML(개인정보 없음)로 검증한다."""
import json

import httpx
import pytest

from crawler import cnu_api, collect as C, k2web, plus
from crawler.common import is_allowed_url, load_sites, mask_pii, parse_date

K2_BOARD = "https://computer.cnu.ac.kr/computer/notice/bachelor.do"
PLUS_BOARD = "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0701&site_dvs_cd=kr&menu_dvs_cd=0701"


def k2_row(no, title, date, pinned=False):
    return f"""<tr class="{'b-top-box' if pinned else ''}"><td class="b-num-box">{'공지' if pinned else no}</td>
      <td class="b-td-left"><div class="b-title-box">
        <a href="?mode=view&amp;articleNo={no}&amp;article.offset=0&amp;articleLimit=10" title="{title} 자세히 보기">
          {title}
        </a><div class="b-m-con"><span class="b-date"> {date} </span></div></div></td><td>{date}</td></tr>"""


def k2_list(*rows):
    return f'<table class="board-table"><tbody>{"".join(rows)}</tbody></table>'


K2_VIEW = """<table><tr><td class="b-title-box">제목</td></tr>
<tr><td><div class="fr-view"><p>신청 기간: 11.9.(월)~11.10.(화)</p><p>문의: 042-821-0000, help@cnu.ac.kr</p>
<p>2025-2026학년도 대상<br>끝</p></div></td></tr>
<tr><th>첨부</th><td><div class="b-file-box">
<a href="?mode=download2&amp;articleNo=1&amp;attachNo=11">1. 안내문.hwp</a>
<a href="?mode=download2&amp;articleNo=1&amp;attachNo=11">1. 안내문.hwp</a>
<a href="https://evil.example.com/x?mode=download">2. 외부.pdf</a></div></td></tr></table>"""


def test_k2web_list_marks_pinned_and_parses_fields():
    html = k2_list(k2_row(100, "[수강] 수강신청 안내", "26.11.03", pinned=True), k2_row(99, "장학 안내", "26.10.20"),
                   "<tr><td>등록된 글이 없습니다</td></tr>")
    rows = k2web.parse_list(html, K2_BOARD)
    assert [r["article_no"] for r in rows] == ["100", "99"]
    assert rows[0] == {"article_no": "100", "title": "[수강] 수강신청 안내", "pinned": True, "posted_at": "2026-11-03",
                       "url": K2_BOARD + "?mode=view&articleNo=100"}
    assert rows[1]["pinned"] is False


def test_k2web_view_masks_pii_and_keeps_school_attachments_once():
    v = k2web.parse_view(K2_VIEW, K2_BOARD + "?mode=view&articleNo=1")
    assert "신청 기간: 11.9.(월)~11.10.(화)" in v["content"]
    assert "[전화번호]" in v["content"] and "[이메일]" in v["content"]
    assert "042-821" not in v["content"] and "@" not in v["content"]
    assert "2025-2026학년도" in v["content"]  # 연도 범위는 전화번호가 아니다
    assert v["attachments"] == [{"name": "안내문.hwp", "url": K2_BOARD + "?mode=download2&articleNo=1&attachNo=11"}]


PLUS_LIST = """<table><tbody>
<tr><td class="num nt">공지</td><td class="title nt"><a href="./?mode=V&amp;no=2515373&amp;code=sub07_0701">게시판 폐쇄 안내</a></td>
<td class="center nt">전체관리자</td><td class="date nt">2026-09-15</td></tr>
<tr><td class="num">1527</td><td class="title"><a href="./?mode=V&amp;no=2516128&amp;code=sub07_0701">숏폼 공모전 안내</a><img alt="NEW"></td>
<td class="center">대외협력실</td><td class="date">2026-11-05</td></tr>
</tbody></table>"""

PLUS_VIEW = """<div id="txt"><div class="board_viewTit"><h4>셔틀버스 휴차 알림</h4></div>
<ul class="board_viewInfo"><li class="date"><span>등록일</span>2026-11-04 16:47:16</li>
<li class="file"><span>파일</span><div><a href="common/download.php?code=sub07_0701&amp;ntt_no=2516119&amp;atch_no=1" title="안내문.pdf">안내문.pdf</a></div></li></ul>
<div class="board_viewDetail board_pdf_viewer"><iframe src="/_module/pdfjs/web/viewer.html?file=/x.pdf"></iframe></div>
<div class="board_viewDetail"><p>&nbsp;</p><br/></div></div>"""


def test_plus_list_and_view():
    rows = plus.parse_list(PLUS_LIST, PLUS_BOARD)
    assert [(r["article_no"], r["pinned"], r["posted_at"]) for r in rows] == [
        ("2515373", True, "2026-09-15"), ("2516128", False, "2026-11-05")]
    assert rows[1]["url"] == PLUS_BOARD + "&mode=V&no=2516128"
    v = plus.parse_view(PLUS_VIEW, rows[1]["url"])
    assert v["content"] == ""  # PDF 뷰어만 있는 글: 본문 없음, 첨부로 남는다
    assert v["attachments"] == [{"name": "안내문.pdf",
                                 "url": "https://plus.cnu.ac.kr/_prog/_board/common/download.php?code=sub07_0701&ntt_no=2516119&atch_no=1"}]


@pytest.mark.parametrize("text,expected", [
    ("26.11.03", "2026-11-03"), ("2026-11-04", "2026-11-04"), ("2026.11.03 10:00", "2026-11-03"), ("", None)])
def test_parse_date(text, expected):
    assert parse_date(text) == expected


def test_mask_pii_variants():
    assert mask_pii("(042)821-1234 / 821-1234 / 1588-0000") == "[전화번호] / [전화번호] / [전화번호]"
    assert mask_pii("기간 2026.11.03~11.10, 09:30") == "기간 2026.11.03~11.10, 09:30"


def test_domain_allowlist_and_sites_config(tmp_path):
    assert is_allowed_url("https://biz.cnu.ac.kr/x.do") and not is_allowed_url("https://cnu.ac.kr.evil.com/")
    assert {s["site"] for s in load_sites()} == {"cnu", "computer", "biz"}
    bad = tmp_path / "sites.json"
    bad.write_text(json.dumps([{"site": "x", "name": "x", "parser": "k2web",
                                "boards": [{"board": "b", "name": "b", "url": "https://example.com/a.do"}]}]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_sites(bad)


def test_api_rows_match_html_shape():
    rows = cnu_api.to_rows([
        {"article_no": 1, "article_title": " 옛 글 ", "article_text": "<p>a@b.cnu.ac.kr</p>", "attach_cnt": 2,
         "update_dt": {"time": 1793000000000}},
        {"article_no": 2, "article_title": "수정일 없는 글", "article_text": "", "update_dt": None},
    ], K2_BOARD, k2web.view_url)
    assert rows[0]["article_no"] == "1" and rows[0]["title"] == "옛 글"
    assert rows[0]["url"] == K2_BOARD + "?mode=view&articleNo=1"
    assert rows[0]["content"] == "[이메일]" and rows[0]["attach_count"] == 2
    assert rows[1]["posted_at"] is None


class StubFetcher:
    """URL → HTML 사전. 등록되지 않은 URL은 로그인 리다이렉트처럼 실패한다."""

    def __init__(self, pages):
        self.pages, self.calls, self.seen = pages, 0, []

    def get(self, url, respect_robots=True):
        self.calls += 1
        self.seen.append(url)
        if url not in self.pages:
            raise PermissionError("리다이렉트됨")
        return self.pages[url]

    def close(self):
        pass


SITE = {"site": "computer", "name": "컴퓨터인공지능학부", "parser": "k2web",
        "boards": [{"board": "bachelor", "name": "학사공지", "url": K2_BOARD}]}


def test_crawl_board_limit_reuse_and_per_post_failure():
    board = SITE["boards"][0]
    page1 = k2_list(k2_row(9, "고정", "26.01.01", True), *(k2_row(n, f"글{n}", "26.11.01") for n in (8, 7, 6)))
    pages = {k2web.list_url(K2_BOARD, 1): page1,
             k2web.view_url(K2_BOARD, "9"): K2_VIEW, k2web.view_url(K2_BOARD, "8"): K2_VIEW}
    prev = {"computer:bachelor:7": {"title": "글7", "content": "이전 본문", "attachments": [], "collected_at": "t0"}}
    f = StubFetcher(pages)
    posts = C.crawl_board_html(f, SITE, board, limit=2, prev_by_id=prev)
    assert [p["article_no"] for p in posts] == ["9", "8", "7"]  # 고정 공지 + 최신 2건
    assert posts[2]["content"] == "이전 본문" and k2web.view_url(K2_BOARD, "7") not in f.seen  # 받은 글은 재요청 안 함
    assert posts[0]["id"] == "computer:bachelor:9" and posts[0]["method"] == "html"

    f2 = StubFetcher({k2web.list_url(K2_BOARD, 1): page1})  # 글 보기가 전부 로그인 필요
    posts = C.crawl_board_html(f2, SITE, board, limit=1, prev_by_id={})
    assert all(p["content"] is None and "content_error" in p for p in posts)

    f3 = StubFetcher({k2web.list_url(K2_BOARD, 1): page1})
    posts = C.crawl_board_html(f3, SITE, {**board, "fetch_body": False}, limit=1, prev_by_id={})
    assert f3.calls == 1 and all(p["content"] is None and "content_error" not in p for p in posts)


def test_collect_keeps_previous_posts_when_board_fails(tmp_path, monkeypatch):
    sites_file = tmp_path / "sites.json"
    sites_file.write_text(json.dumps([SITE], ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "html"
    out.mkdir()
    old = {"id": "computer:bachelor:1", "board": "bachelor", "title": "지난 글", "posted_at": "2026-10-01", "also_in": ["x"]}
    (out / "computer.json").write_text(json.dumps({"posts": [old]}), encoding="utf-8")
    monkeypatch.setattr(C, "Fetcher", lambda: StubFetcher({}))  # 목록부터 실패
    report = C.collect("html", data_dir=tmp_path, sites_file=sites_file)
    saved = json.loads((out / "computer.json").read_text(encoding="utf-8"))
    assert saved["ok"] is False and [p["id"] for p in saved["posts"]] == ["computer:bachelor:1"]
    assert "also_in" not in saved["posts"][0]
    assert report["sites"]["computer"]["boards"]["bachelor"]["kept_previous"] == 1
    assert (out / "_report.json").exists()


def test_collect_api_requires_key(monkeypatch, tmp_path):
    monkeypatch.delenv("CNU_KEY", raising=False)
    with pytest.raises(RuntimeError):
        C.collect("api", data_dir=tmp_path)


def test_dedupe_merges_cross_posted_notice():
    a = {"id": "s:a:1", "board": "a", "title": "같은 공지", "posted_at": "2026-11-01"}
    b = {"id": "s:b:2", "board": "b", "title": "같은 공지", "posted_at": "2026-11-01"}
    c = {"id": "s:b:3", "board": "b", "title": "다른 공지", "posted_at": "2026-11-01"}
    out = C.dedupe([a, b, c])
    assert [p["id"] for p in out] == ["s:a:1", "s:b:3"] and out[0]["also_in"] == ["b"]


def test_compare_counts_api_only_within_html_window(tmp_path):
    def p(no, date, title="t", pinned=False, content="x"):
        return {"id": f"computer:bachelor:{no}", "site": "computer", "board": "bachelor", "title": title,
                "posted_at": date, "pinned": pinned, "content": content}
    for method, posts in {
        "html": [p(1, "2025-01-01", pinned=True), p(5, "2026-11-01"), p(4, "2026-10-20", title="old")],
        "api": [p(5, "2026-11-01"), p(4, "2026-10-20", title="new"), p(3, "2026-10-25"), p(2, "2026-09-01")],
    }.items():
        (tmp_path / method).mkdir()
        (tmp_path / method / "computer.json").write_text(json.dumps({"posts": posts}), encoding="utf-8")
    [row] = C.compare(tmp_path)
    assert row["both"] == 2 and row["html_only"] == ["computer:bachelor:1"]
    assert row["api_only_in_window"] == ["computer:bachelor:3"]  # 9월 글은 HTML 수집 범위 밖이라 제외
    assert row["title_diff"] == ["computer:bachelor:4"]


def test_fetch_board_never_puts_key_in_url():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["body"] = str(request.url), request.content.decode()
        return httpx.Response(200, json={"RESULT": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        assert cnu_api.fetch_board(c, "SECRET", 305) == []
    assert "SECRET" not in seen["url"] and "AUTH_KEY=SECRET" in seen["body"] and "P_board_no=305" in seen["body"]
