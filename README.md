# 캠퍼스 픽 (가칭) — 맞춤형 교내 정보 큐레이션 도구

흩어진 충남대 공지·장학·취업 정보를 모아 학생 관심사에 맞게 보여주는 싱크인사이트 위젯 도구(실무 프로젝트 랩 10조).
기획은 `수행계획서_교내정보큐레이션.docx` 참고.

**현재 단계: 수집기와 웹 목록 데모.** 충남대 본부, 컴퓨터인공지능학부, 경영학부 게시판을 크롤링해 JSON으로 저장한다(DB가 생기기 전까지 JSON 파일이 저장소 역할을 한다). 웹 화면에서는 홈페이지별 공지를 목록으로 보여준다.

## 구조
```
core/                     Core(Python) 축
  crawler/
    sites.json            수집 대상 사이트·게시판 (코드 수정 없이 교체 가능)
    common.py             요청(간격·robots·학교 도메인 제한), 본문 정제, 개인정보 마스킹
    k2web.py              학과 홈페이지(K2Web CMS) 파서: computer·biz
    plus.py               본부 홈페이지(plus.cnu.ac.kr/_prog/_board) 파서
    cnu_api.py            학교 공식 게시판 API 수집 (CNU_KEY)
    collect.py            수집 실행·저장·리포트·HTML/API 비교 + CLI
  tests/                  단위 테스트(네트워크 없음)
  crawl_demo.ipynb        데모 노트북
  web/index.html          웹 목록 데모 (정적 페이지, data/*.json을 읽음)
  data/                   수집 결과 JSON (git 제외)
docs/                     PROJECT_CONTEXT.md(장기 정보), AI_HANDOFF.md(진행 상황)
```

## 수집 대상
| site | 사이트 | 게시판 | 방식 |
|---|---|---|---|
| `cnu` | 충남대 본부 plus.cnu.ac.kr | 새소식, 학사정보, 장학게시판 | HTML (API 번호 미확인) |
| `computer` | 컴퓨터인공지능학부 computer.cnu.ac.kr | 학사공지, 교내 일반소식, 교외 활동·인턴·취업(목록만, 본문은 로그인 필요), 사업단소식 | HTML / API 305·307·324 (교내 일반소식 번호 미확인) |
| `biz` | 경영학부 biz.cnu.ac.kr | 학부 공지사항, 취업정보 | HTML / API 3792 |

> **robots.txt 주의:** plus.cnu.ac.kr은 robots.txt로 일반 크롤러를 전부 막는다(`Disallow: /`).
> 공식 API 키 발급 전까지만 HTML로 저빈도 수집하기로 팀에서 결정했다(`sites.json`의 `respect_robots: false`).
> 키를 발급받으면 API 결과와 비교한 뒤 본부 게시판은 API로 전환한다. 학과 사이트는 robots를 확인하고 지킨다.

## 실행
```bash
cd core
pip install -r requirements.txt

jupyter notebook crawl_demo.ipynb                 # 데모 노트북
python -m crawler.collect --method html --limit 10  # CLI: HTML 수집
python -m pytest -q tests                          # 테스트
```

### 웹 목록 데모
```bash
cd core
python -m crawler.collect --limit 10              # 1) 수집 → data/html/*.json
python -m http.server 8000 --bind 127.0.0.1       # 2) 정적 서버 (Python 기본 내장)
# 3) 브라우저에서 http://127.0.0.1:8000/web/
```
- 탭으로 충남대학교(본부)·컴퓨터인공지능학부·경영학부를 고르고, 게시판 필터와 제목·본문 검색을 쓸 수 있다. 상단 고정 공지가 먼저 나오고 나머지는 최신순이다.
- 항목마다 게시판·고정 여부·게시일·첨부 수가 보이고, 본문 미리보기를 펼칠 수 있다. 원문 링크는 새 탭에서 연다(`rel="noopener noreferrer"`, 학교 도메인만).
- `http://127.0.0.1:8000/web/?method=api`로 열면 공식 API 수집 결과를 본다. `#biz`처럼 해시를 붙이면 해당 탭이 바로 열린다.
- 브라우저 보안 정책 때문에 `index.html`을 파일로 직접 열면 JSON을 읽지 못한다. 반드시 서버로 연다.
공식 API(키 발급 후, 키는 환경변수로만 넣는다):
```powershell
$env:CNU_KEY = "<발급키>"
python -m crawler.collect --list-api-boards   # 본부 게시판 번호 찾기 → sites.json api_board_no
python -m crawler.collect --method api
python -m crawler.collect --compare           # HTML vs API 결과 비교
```

### 환경변수
| 이름 | 용도 |
|---|---|
| `CNU_KEY` | 학교 공식 게시판 API 발급키 (API 수집 시에만) |
| `CAMPUS_PICK_SITES_FILE` | 수집 대상 설정 파일 경로 (기본 `core/crawler/sites.json`) |

## 출력 JSON
`core/data/{html|api}/{site}.json`
```json
{"site": "computer", "name": "컴퓨터인공지능학부", "method": "html", "updated": "2026-11-05T19:50:39+09:00", "ok": true,
 "posts": [{
   "id": "computer:bachelor:602526", "site": "computer", "site_name": "컴퓨터인공지능학부",
   "board": "bachelor", "board_name": "학사공지", "article_no": "602526",
   "title": "...", "url": "https://computer.cnu.ac.kr/computer/notice/bachelor.do?mode=view&articleNo=602526",
   "posted_at": "2026-11-03", "pinned": true,
   "content": "본문 텍스트(이메일·전화번호 마스킹)", "attachments": [{"name": "안내.hwp", "url": "..."}],
   "method": "html", "collected_at": "2026-11-05T19:50:39+09:00"}]}
```
- `content`: `""`이면 본문이 이미지·PDF뿐인 글이고, `null`이면 본문을 받지 않은 글이다(로그인 필요 등. `content_error`에 이유).
- `also_in`: 같은 공지(제목·게시일 동일)가 다른 게시판에도 있으면 그 게시판 id.
- API 결과에는 `pinned: null`, `attachments: []`, `attach_count`가 들어가고, `posted_at`은 수정일 기준이다.
- `_report.json`: 게시판별 수집 건수·신규 건수·오류. 0건이면 경고 로그를 남긴다.
- 작성자는 개인정보라서 저장하지 않는다.

## 참고 자료
수집기는 **[zer8m/whalecrew2](https://github.com/zer8m/whalecrew2)** (앗!차차, 충남대 학과 공지 마감일 수집 웨일 확장앱)를 참고해 Python으로 새로 작성했다. 코드를 복사하지는 않았다. 참고한 부분은 다음과 같다.

| 참고한 곳 (whalecrew2) | 가져온 내용 | 반영 위치 |
|---|---|---|
| `extension/departments.json` | 컴퓨터인공지능학부(305 학사공지·307 취업정보·324 사업단소식)와 경영학부(3792) 게시판 번호·URL | `core/crawler/sites.json` |
| `collector/collect.js` `post`·`fetchBoard` | 공식 API 주소와 호출 방식(키가 URL에 남지 않게 POST form `AUTH_KEY`·`P_board_no` 사용), 응답 필드, `update_dt` 누락 대응, 최신 50건 | `core/crawler/cnu_api.py`, `collect.py` |
| `collector/collect.js` `main` | 게시판 목록 API(`cmsBoard`), 실패한 게시판은 지난 수집분 유지, `_report.json` 점검 리포트, 전부 실패 시 종료 코드 1 | `collect.py` `collect`·`main` |
| `collector/collect.js` `mergeSame` | 여러 게시판에 올라온 같은 공지 병합 | `collect.py` `dedupe` |
| `collector/build-map.js` `crawl` | 학교 사이트 요청 간격 1초(빠르게 요청하면 일시 거부) | `common.py` `REQUEST_INTERVAL` |
| `extension/extract.js` `htmlText`·`splitDrag` | 본문 HTML을 줄 단위 텍스트로 바꾸는 방식, 전화번호 가리기 | `common.py` `html_to_text`·`mask_pii` |

HTML 파서(`k2web.py`, `plus.py`)는 whalecrew2에 없다(그쪽은 API만 사용). 2026-11-05에 실제 게시판 구조를 확인하고 새로 작성했다.
