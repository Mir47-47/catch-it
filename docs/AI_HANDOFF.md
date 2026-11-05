# AI_HANDOFF

## 현재 상태
- 작업: Core 수집기 데모. 충남대 본부·컴퓨터인공지능학부·경영학부 게시판을 HTML로 크롤링해 JSON으로 저장하고, 노트북으로 시연한다.
- 브랜치: `main` (2026-11-05 로컬 저장소 새로 만듦, 원격 없음)

## 완료
- `core/crawler/`: `sites.json`(3개 사이트·8개 게시판), `common.py`, `k2web.py`, `plus.py`, `cnu_api.py`, `collect.py`(CLI 포함)
- `core/crawl_demo.ipynb`: 대상 확인 → HTML 수집 → 요약 표·샘플 JSON → API 수집(키 있을 때) → 비교
- `core/tests/test_crawler.py`: 합성 HTML 기반 16개 테스트
- README(whalecrew2 참고 위치 표 포함), docs 2종

## 검증
- `python -m pytest -q tests` → 16 passed (Python 3.12.7, 로컬)
- 실제 수집(2026-11-05): `--limit 3` 1회차 50 요청, 2회차 12 요청(본문 재사용 확인). 노트북 nbclient 전체 실행은 84초, 61건, 63 요청, 오류 없음.
- 미검증
  - 공식 API 경로 전체: 키가 없다. `fetch_board`가 키를 URL에 넣지 않는 것만 모의 테스트로 확인했다.
  - plus 글번호와 API `article_no`가 같은지
  - Python 3.11(계획서 기준 버전)에서의 실행

## 문제·주의
- plus.cnu.ac.kr robots.txt `Disallow: /`이다. 사용자 결정으로 API 발급 전까지만 HTML 수집한다. 수집 빈도를 높이지 말 것.
- computer 취업정보 글 보기는 로그인이 필요하다 → `fetch_body: false`. 다른 게시판에서도 회원 전용 글은 `content: null` + `content_error`로 남고 다음 수집 때 다시 시도한다.
- `crawler/__init__.py`에서 `collect` 함수를 다시 내보내지 말 것. `crawler.collect` 모듈 이름을 가려 `from crawler import collect`가 함수를 돌려주게 된다(테스트가 깨졌던 원인).
- 본문 없는 글(이미지·PDF뿐)이 꽤 많다. 특히 본부 학사정보. 분류 단계에서 제목과 첨부 이름을 활용해야 한다.

## 다음 작업 (우선순위)
1. `CNU_KEY`를 발급받으면 `--list-api-boards`로 본부 게시판 번호를 찾아 sites.json `api_board_no`에 넣는다. 이어서 `--method api` → `--compare`로 비교하고, 결과에 따라 본부 수집 방식을 정한다.
2. 분류 단계: 키워드 규칙 카테고리(장학/취업/행사/학사/비교과), 대상 학과·학년, 마감일 추출. 마감일은 whalecrew2 `extension/extract.js` 규칙을 참고한다.
3. Core FastAPI 골격(`POST /tools/campus-pick/crawl`)에서 `crawler.collect.collect()`를 호출하고, Poetry(pyproject)로 옮긴다.
4. BeautifulSoup 사용 여부를 싱크인사이트와 협의한다.

## Git
- 커밋: 이 문서와 함께 첫 커밋. 원격 저장소가 없어 push하지 않았다.
- 제외: `core/data/`(수집 결과)
