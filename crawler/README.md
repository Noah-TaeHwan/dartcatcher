# 크롤러 (crawl4ai / Docker)

퀀트 데이터 파이프라인의 수집 계층. 금융 공시 데이터를 정기적으로 긁어오기 위한 구성요소로,
크롤링 엔진을 로컬에 직접 설치하지 않고 Docker 이미지로 격리해 실행한다.

## 크롤링 도커 이미지란

헤드리스 브라우저(Chromium)와 크롤링 엔진, 그 의존성 전체를 하나의 컨테이너 이미지로 묶어
`docker run` 한 번으로 크롤링 서버를 띄울 수 있게 만든 실행 패키지다.

## 왜 crawl4ai 인가

| 후보 | 판단 |
| --- | --- |
| **crawl4ai** (채택) | 헤드리스 브라우저로 JS 렌더링을 처리하면서, 결과를 LLM 파이프라인에 바로 넣기 좋은 마크다운으로 변환해준다. REST API 서버 모드를 이미지가 기본 제공해 수집 계층을 언어 중립적으로 분리할 수 있다. |
| Splash | JS 렌더링은 되지만 출력이 HTML/PNG 수준이라 본문 추출·마크다운 변환을 별도로 붙여야 한다. Scrapy 연동 전제의 설계라 단독 REST 수집기로 쓰기엔 군더더기가 있다. |
| python + requests/bs4 | 정적 HTML에는 가장 가볍고 빠르지만 JS로 채워지는 화면을 못 읽는다. 실제로 이번 대상 화면이 여기에 해당했다(아래 참고). |

다만 아래 "실행 중 마주친 제약"에 적었듯 crawl4ai도 만능은 아니었고 JS 실행이 필요한
경로는 보안 정책 때문에 막혀서 우회해야 했다.

## 1. 이미지 받기

```bash
docker pull unclecode/crawl4ai:latest
```

실제 출력 발췌:

```
Digest: sha256:bd36741e7bdd35ddc1a05d9183e1d6d8cefb61dd640d944a25d026b76e917690
Status: Downloaded newer image for unclecode/crawl4ai:latest
docker.io/unclecode/crawl4ai:latest
```

크기(측정 환경: Docker 29.6.2, macOS arm64):

```bash
$ docker images unclecode/crawl4ai --format '{{.Tag}} {{.ID}} {{.Size}}'
latest bd36741e7bdd 9.06GB

$ docker image inspect unclecode/crawl4ai:latest --format '{{.Os}}/{{.Architecture}} {{.Size}}'
linux/arm64 2199628718
```

두 값이 다르다. `docker images`는 9.06GB, `docker image inspect`의 `.Size`는 약 2.2GB로
보고한다. 어느 쪽이 디스크 실사용량인지는 확인하지 못했으므로 두 명령의 출력을 그대로 남긴다.

## 2. 컨테이너 실행

이미지의 기본 설정은 `127.0.0.1`에만 바인딩한다(`/app/config.yml`의 `app.host`).
그래서 포트만 매핑하면 호스트에서 접속이 안 되고 실제로 처음 실행했을 때 헬스체크가 실패했다.
`GUNICORN_BIND`로 바인드 주소를 바꿔야 하는데, 이미지가 **인증 토큰 없이 비루프백으로
여는 것을 거부**하므로 `CRAWL4AI_API_TOKEN`을 함께 넘긴다.

```bash
# 토큰을 생성해 .env(=gitignore 대상)에 저장
printf 'CRAWL4AI_API_TOKEN=%s\n' "$(openssl rand -hex 32)" > .env
chmod 600 .env

set -a; . ./.env; set +a
docker run -d --name crawl4ai-w1 -p 11235:11235 --shm-size=1g \
  -e GUNICORN_BIND=0.0.0.0:11235 \
  -e CRAWL4AI_API_TOKEN="$CRAWL4AI_API_TOKEN" \
  unclecode/crawl4ai:latest
```

`--shm-size=1g`는 Chromium이 기본 64MB 공유메모리에서 죽는 것을 막기 위한 것이다.
토큰 값은 저장소에 커밋하지 않는다(`.env`는 `.gitignore`에 등재되어 있고
`git check-ignore -v .env`로 확인했다).

### 헬스체크

```bash
$ curl -H "Authorization: Bearer $CRAWL4AI_API_TOKEN" http://localhost:11235/health
{"status":"ok","timestamp":1785890235.3374875,"version":"0.9.2"}

$ docker ps --filter name=crawl4ai-w1 --format '{{.Image}} | {{.Status}} | {{.Ports}}'
unclecode/crawl4ai:latest | Up 12 seconds (healthy) | 0.0.0.0:11235->11235/tcp, [::]:11235->11235/tcp
```

## 3. robots.txt 확인

크롤 전에 대상 사이트의 robots.txt를 실제로 받아서 확인했다.

```bash
$ curl https://dart.fss.or.kr/robots.txt
```

응답 전문(HTTP 200, `Content-Length: 204`):

```
User-agent: *
Disallow: /dsaf001/main.do
Disallow: /report/viewer.do
Disallow: /report/download.do
Disallow: /pdf/download/
Disallow: /dsae001/selectPopup.ax
Disallow: /html/search/SearchCompany_M2.html
```

판단:

- `Crawl-delay`, `Sitemap` 지시자는 없다.
- 이번에 수집한 경로는 **`/dsab007/detailSearch.ax`(공시 목록)** 이며 Disallow 목록 어디에도
  해당하지 않는다. → 허용.
- 반대로 `Disallow: /dsaf001/main.do`는 **개별 공시 원문 뷰어**다. 목록에 그 링크가 포함되어
  있지만 **따라 들어가지 않았다.** 목록 페이지만 수집하고 멈춘다.
- `Disallow: /dsae001/selectPopup.ax`(기업개황 팝업)도 마찬가지로 따라가지 않았다.

### robots.txt 자동 확인

이 판단은 손으로 한 번 한 뒤 코드로 승격했다. `crawler/robots_check.py` 가 표준
`urllib.robotparser` 로 대상 URL을 robots.txt 규칙과 대조하고, 하나라도 금지면 크롤링을
시작하기 전에 중단한다. 원문은 `crawler/sites.json` 의 `robots_source` 로 지정하며, 로컬
파일(기본 `evidence/dart_robots.txt`, 네트워크 요청 없음) 또는 실시간 `/robots.txt` URL
둘 다 지원한다. 확인만 하고 끝내려면 아래처럼 돌린다:

```bash
python3 crawler/crawl_dart.py --check-only
# [robots] DART 전자공시 목록 (dart.fss.or.kr) 대상 URL 3건 전부 허용 확인됨
```

robots.txt가 URL을 금지하면 비영(非零) 종료 코드로 멈춘다.

DART가 허용되었으므로 폴백 대상(`https://quotes.toscrape.com`)은 사용하지 않았다.

## 4. 크롤 실행

```bash
python3 crawler/crawl_dart.py
```

실제 출력:

```
[crawl] 1페이지 요청 중...
[ok] 1페이지 status=200 공시건수=15 md=4983자
[crawl] 2페이지 요청 중...
[ok] 2페이지 status=200 공시건수=15 md=5564자
[crawl] 3페이지 요청 중...
[ok] 3페이지 status=200 공시건수=15 md=5386자
```

스크립트가 내부적으로 호출하는 REST API는 다음과 같다.

```bash
curl -X POST http://localhost:11235/crawl \
  -H "Authorization: Bearer $CRAWL4AI_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"urls":["https://dart.fss.or.kr/dsab007/detailSearch.ax?currentPage=1&maxResults=15"],
       "browser_config":{"type":"BrowserConfig","params":{"headless":true}},
       "crawler_config":{"type":"CrawlerRunConfig","params":{"cache_mode":"BYPASS"}}}'
```

응답 요약(실제 실행 결과):

```json
{
  "success": true,
  "status_code": 200,
  "url": "https://dart.fss.or.kr/dsab007/detailSearch.ax?currentPage=1&maxResults=15",
  "markdown_chars": 4994
}
```

수집된 마크다운 첫 행 예시(`data/crawl/dart_page1.md`):

```
공시서류검색 목록
| 번호 | 공시대상회사 | 보고서명 | 제출인 | 접수일자 | 비고 |
| 1 | 코 NH농우바이오 | 지급수단별ㆍ지급기간별지급금액및분쟁조정기구에관한사항 | NH농우바이오 | 2026.08.05 | 공 |
```

3개 페이지에서 접수번호(`rcpNo`) 기준 각 15건, 총 45건을 얻었고 페이지 간 중복은 없었다.

## 실행 중 마주친 제약 (실패 기록)

1. **`dsab007/main.do`를 그대로 열면 목록이 비어 있다.** 렌더링은 되지만 표에
   "조회 결과가 없습니다"만 나온다. 목록을 서버가 HTML에 심어주지 않고 페이지 로드 후 AJAX로
   채우기 때문이다. `requests`+`bs4`로도 같은 이유로 실패한다(원본 HTML에 `rcpNo`가 0건).
2. **페이지의 `search()` 함수를 브라우저에서 호출하려 했으나 막혔다.** crawl4ai 0.9.2는
   신뢰되지 않은 요청 본문이 `js_code`를 지정하는 것을 금지한다:

   ```
   {"detail":"Rejected config: field 'js_code' is not permitted on CrawlerRunConfig from an untrusted request"}
   ```

   이건 이미지의 의도된 보안 경계라서 끄지 않았다.
3. **우회:** 화면이 내부적으로 호출하는 것과 같은 목록 엔드포인트
   `dsab007/detailSearch.ax`가 GET 쿼리스트링으로도 응답하는 것을 확인하고 그 주소를
   crawl4ai로 직접 열었다. JS 실행 없이 목록 HTML이 그대로 오므로 `js_code`가 필요 없다.

## 크롤링 윤리 준수 사항

- **robots.txt 자동 확인**: 수집 전 `robots_check.py` 가 대상 URL을 robots.txt 규칙과
  대조하고 금지되면 중단한다. 원문·대상 URL은 `crawler/sites.json` 에서 읽는다.
- **요청 간격**: 페이지 사이 기본 2.5초 대기(`crawler/sites.json` 의
  `request_interval_sec`). robots.txt에 `Crawl-delay`가 없어 자체 기준(2초 이상)을 정해
  적용했다.
- **수집 범위 제한**: 1~3페이지, 페이지당 15건까지만(`sites.json` 의 `pages`·
  `list_url_template`). 전체 아카이브를 훑지 않는다.
- **Disallow 경로 미접근**: 공시 원문 뷰어(`/dsaf001/main.do`)와 기업개황 팝업
  (`/dsae001/selectPopup.ax`)은 목록에 링크가 있어도 따라가지 않는다.
- **동시 요청 없음**: 순차 실행. 병렬 요청을 보내지 않는다.
- **캐시**: `cache_mode: BYPASS`는 crawl4ai 로컬 캐시를 끄는 옵션이며 재실행 시 불필요한
  재요청이 걱정된다면 이 값을 조정하는 편이 대상 서버에 더 낫다.
- **공개 데이터만**: 로그인·인증이 필요한 영역은 건드리지 않았다.

## 대상 사이트 설정 (sites.json)

`crawler/crawl_dart.py` 는 코드에 URL 상수를 두지 않고 `crawler/sites.json` 에서 대상을
읽어 크롤링한다. 다른 사이트를 추가하려면 `sites` 아래에 새 키를 넣고
`python3 crawler/crawl_dart.py --site <키>` 로 실행하면 된다. 기본 `--site dart` 는 기존
DART 목록과 동일하게 동작한다. `--config` 로 설정 파일 경로도 바꿀 수 있다.

| 필드 | 의미 |
| --- | --- |
| `label` | 실행 로그에 표시할 사이트 이름 |
| `user_agent` | robots.txt `can_fetch` 판정에 쓸 사용자 에이전트 |
| `robots_source` | robots.txt 원문의 로컬 파일 경로 또는 http(s) URL |
| `list_url_template` | `{page}` 자리표를 가진 목록 URL 템플릿 |
| `request_interval_sec` | 페이지 간 최소 대기(초) |
| `pages` | 크롤할 페이지 번호 목록 |
| `page_timeout`, `delay_before_return_html` | crawl4ai 렌더링 옵션 |

## 산출물 경로

| 경로 | 내용 |
| --- | --- |
| `crawler/crawl_dart.py` | 수집 스크립트(표준 라이브러리만 사용) |
| `crawler/robots_check.py` | robots.txt 자동 확인 모듈 |
| `crawler/sites.json` | 대상 사이트 URL·robots·요청 간격 설정 |
| `crawler/test_crawl_site.py` | robots 허용·거부, 설정 분리 테스트 |
| `crawler/README.md` | 이 문서 |
| `data/crawl/dart_page1.md` ~ `dart_page3.md` | 페이지별 마크다운 본문 |
| `data/crawl/dart_page1.json` ~ `dart_page3.json` | 페이지별 메타데이터(상태코드, 수집시각, 접수번호 표본) |
| `data/crawl/dart_summary.json` | 3개 페이지 수집 요약 |
| `evidence/dart_robots.txt` | robots.txt 원문 |
| `evidence/dart_robots_headers.txt` | robots.txt 응답 헤더 |
| `evidence/image_info.txt` | 이미지 크기·다이제스트 |
| `evidence/health.txt`, `evidence/docker_ps.txt` | 헬스체크·컨테이너 상태 |
| `evidence/crawl_run.txt`, `evidence/api_call_sample.txt` | 크롤 실행 로그·API 응답 |
| `.env` | crawl4ai 토큰. **gitignore 대상이며 커밋하지 않는다.** |

## 정리

```bash
docker rm -f crawl4ai-w1
```

---

수집 시각: 2026-08-05 (KST). 위 출력은 모두 해당 시점에 실제로 실행한 결과이며,
DART 공시 목록은 시간에 따라 바뀌므로 재실행하면 내용이 달라진다.
