# AI_HANDOFF

## 현재 상태
- 작업: Core 수집기 + 웹 목록 데모. 충남대 본부·컴퓨터인공지능학부·경영학부 게시판을 HTML로 크롤링해 JSON으로 저장하고(DB 대신), 웹 화면에서 홈페이지별 공지 목록으로 보여준다.
- 브랜치: `main` (로컬 저장소, 원격 없음)

## 완료
- `core/crawler/`: `sites.json`(3개 사이트·8개 게시판), `common.py`, `k2web.py`, `plus.py`, `cnu_api.py`, `collect.py`(CLI 포함)
- `core/crawl_demo.ipynb`: 대상 확인 → HTML 수집 → 요약 표·샘플 JSON → API 수집(키 있을 때) → 비교
- `core/web/index.html`: 사이트 탭, 게시판 필터, 검색, 고정 공지 우선·최신순, 본문 미리보기·첨부, `?method=api`, `#site` 해시
- `core/tests/test_crawler.py`: 합성 HTML 기반 16개 테스트
- README(실행법, whalecrew2 참고 위치 표), docs 2종

## 검증
- `python -m pytest -q tests` → 16 passed (Python 3.12.7)
- 실제 수집(2026-11-05): `--limit 10` → 101건(본부 35, 컴퓨터 39, 경영 27). 새 글 40건만 받아 45회 요청했다(증분 동작 확인). 노트북 nbclient 전체 실행은 오류 없음.
- 웹 데모: headless Chrome으로 확인
  - 화면: 데스크톱, 375px iframe 스크린샷
  - 상호작용: 같은 출처 wrapper 페이지에서 조작해 기대값과 일치함을 확인. 탭 3개 건수, 게시판 필터(사업단소식 10), 검색(DevFast 2), 결과 없음 문구, 탭 전환·해시, 링크 50개 전부 새 탭·학교 도메인, 미리보기 600자 자르기.
  - 참고: headless Chrome의 `--window-size`는 최소 폭이 512px이라 그보다 좁은 폭은 iframe으로 확인해야 한다.
- 미검증
  - 공식 API 경로 전체(키 없음, 모의 테스트만)
  - plus 글번호와 API `article_no`가 같은지
  - Python 3.11
  - 웹 데모의 `?method=api` 실제 데이터

## 문제·주의
- plus.cnu.ac.kr robots.txt `Disallow: /`이다. 사용자 결정으로 API 발급 전까지만 HTML 수집한다. 수집 빈도를 높이지 말 것.
- computer 취업정보 글 보기는 로그인이 필요하다 → `fetch_body: false`. 회원 전용 글은 `content: null` + `content_error`로 남고, 다음 수집 때 다시 시도한다.
- `crawler/__init__.py`에서 `collect` 함수를 다시 내보내지 말 것. `crawler.collect` 모듈 이름을 가린다.
- 본문 없는 글(이미지·PDF뿐)이 많다. 특히 본부 학사정보. 분류할 때 제목·첨부 이름을 활용할 것.
- 웹 데모는 `file://`로 열면 fetch가 막힌다. `core/`에서 http.server로 연다.

## 다음 작업 (우선순위)
1. `CNU_KEY` 발급 후: `--list-api-boards`로 본부 게시판 번호를 찾아 sites.json `api_board_no`에 넣는다 → `--method api` → `--compare` 순으로 비교하고, 웹 `?method=api`로도 확인한다.
2. 분류 단계: 카테고리(장학/취업/행사/학사/비교과), 대상 학과·학년, 마감일 추출(whalecrew2 `extension/extract.js` 참고). 결과가 생기면 웹 데모에 카테고리·D-day를 표시한다.
3. Core FastAPI 골격(`POST /tools/campus-pick/crawl`) + Poetry로 옮긴다.
4. BeautifulSoup 사용 여부를 싱크인사이트와 협의한다.

## Git
- 커밋 2개: 수집기(`0a21100`), 웹 목록 데모(이 문서와 함께). 원격 저장소가 없어 push하지 않았다.
- 제외: `core/data/`(수집 결과)
