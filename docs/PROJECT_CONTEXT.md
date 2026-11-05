# PROJECT_CONTEXT

## 목적
캠퍼스 픽(가칭): 충남대 교내 공지·장학·취업 정보를 수집·분류해 학생 관심사(학과·학년·카테고리·키워드) 일치도 순으로 보여주는 싱크인사이트 위젯 도구. 기획 원본: `수행계획서_교내정보큐레이션.docx`.

## 구조 (계획서 기준 3축)
- Frontend(React) → Backend(Spring Boot, `/api/tools/campus-pick/...`) → Core(FastAPI, `/tools/campus-pick/crawl`, `/recommend`)
- 파이프라인: 크롤링 → 키워드 규칙 분류·대상·마감일 추출 → 추천 점수 → 피드. 벡터화·LLM 분류 없음(피드백 반영해 단순화).
- 현재 구현은 Core 수집기(`core/crawler/`), 데모 노트북, 웹 목록 데모(`core/web/index.html`)다. FastAPI·Backend·Frontend는 아직 없다.
- **DB가 없는 동안에는 `core/data/{html|api}/{site}.json`이 저장소다.** 웹 데모는 정적 페이지가 이 JSON과 `crawler/sites.json`(탭·게시판 목록)을 직접 fetch한다. 서버는 `python -m http.server`이고 의존성은 없다. 계획서의 React 위젯과 Backend API가 생기면 대체되는 임시 화면이라 빌드 도구나 프레임워크를 쓰지 않았다.
- 웹 데모는 데이터를 신뢰하지 않는다. 텍스트는 `textContent`로만 넣고, 링크는 `*.cnu.ac.kr`만 새 탭(`noopener noreferrer`)으로 연다.

## 수집기 설계 결정
- **사이트 설정은 `core/crawler/sites.json`에 둔다.** 계획서 3.5에 따라 수집 대상 URL은 코드에 고정하지 않으며, `CAMPUS_PICK_SITES_FILE`로 교체할 수 있다. `parser` 값(`k2web`|`plus`)으로 파서를 고른다.
- **파서는 CMS별로 나눴다.** 학과 사이트는 K2Web CMS로 모두 같은 틀이라 `k2web.py` 하나로 처리하고, 본부는 다른 CMS라 `plus.py`를 쓴다. 학과를 추가할 때 K2Web 사이트면 sites.json만 고치면 된다.
- **HTML과 공식 API는 같은 스키마로 저장한다**(`data/html/`, `data/api/`). 키를 받으면 `compare()`로 두 결과를 비교한다(팀 결정, 2026-11-05).
- `id = {site}:{board}:{article_no}`. K2Web의 `articleNo`와 API의 `article_no`는 같은 값이다(whalecrew2가 이 전제로 URL을 만든다). 본부(plus) 글번호가 API 번호와 같은지는 **미확인**이다.
- **예의 있는 수집:** 요청 간격 1초, 1회 재시도, URL은 `*.cnu.ac.kr`만 허용, 리다이렉트(로그인)는 실패로 처리, 이미 받은 글(같은 id·제목)은 본문을 다시 요청하지 않는다.
- **robots.txt:** 학과 사이트는 허용이라 지킨다(`respect_robots: true`). plus.cnu.ac.kr·www.cnu.ac.kr은 `Disallow: /`이다. 팀 결정으로 API 발급 전까지만 HTML 수집(`respect_robots: false`)한다.
- **개인정보:** 작성자는 저장하지 않고, 본문의 이메일·전화번호는 마스킹한다. 수집 결과(`core/data/`)는 git에서 제외한다.
- 실패한 게시판은 지난 수집분을 유지하고, 0건이나 오류가 나면 로그와 `_report.json`에 남긴다. 계획서의 수집 상태 모니터링 항목이다.

## 확인된 사이트 사실 (2026-11-05)
- 인재개발원 job.cnu.ac.kr 게시판은 로그인이 필요하다(302 → login.do). 수집 대상에서 뺐다.
- computer.cnu.ac.kr 취업정보(job.do)는 목록은 공개지만 글 보기는 로그인이 필요하다. 그래서 `fetch_body: false`로 둔다.
- 본문이 이미지나 PDF 뷰어(iframe)뿐인 글이 꽤 많다. 그런 글은 `content: ""`이므로 분류할 때 제목과 첨부 이름을 함께 써야 한다.
- 공식 API 응답에는 고정 공지 여부, 첨부 이름, 작성일이 없고 수정일(`update_dt`)만 있다.

## 명령어
```bash
cd core
pip install -r requirements.txt
python -m pytest -q tests
python -m crawler.collect --method html --limit 10   # --sites cnu,biz / --no-body / --compare / --list-api-boards
```

## 제약 (계획서)
- Core 기준 스택: Python >=3.11,<3.12, FastAPI, Pydantic v2, Poetry, httpx. BeautifulSoup은 싱크인사이트와 사전 협의가 필요하다(미결 사항 4).
- 비밀값(`CNU_KEY` 등)은 환경변수로만 넣고, 문서에는 변수명만 적는다.
