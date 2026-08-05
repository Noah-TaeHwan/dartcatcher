# 브라우저 캡처 (Playwright + Docker)

DART 전자공시시스템 페이지를 헤드리스 브라우저로 접속해 **전체 페이지 스크린샷**을
PNG로 남기는 모듈이다. 실행 환경은 Microsoft가 배포하는 공식 Playwright 파이썬
이미지를 그대로 쓰고, 호스트에는 아무것도 설치하지 않는다.

## 왜 Playwright인가

| 근거 | 내용 |
| --- | --- |
| 공식 이미지 유지보수 | `mcr.microsoft.com/playwright/python` 은 Microsoft가 직접 배포·갱신한다. Playwright 릴리스마다 같은 버전 태그가 함께 올라와 라이브러리와 런타임 버전을 어긋나지 않게 고정할 수 있다. |
| 브라우저 번들 포함 | Chromium·Firefox·WebKit 바이너리와 리눅스 시스템 의존성(폰트, 그래픽 라이브러리)이 이미지 안에 들어 있다. 컨테이너에서 `apt-get` 으로 의존성을 맞추는 과정이 통째로 사라진다. |
| 캡처 API 품질 | `page.screenshot(full_page=True)` 한 줄로 뷰포트 밖까지 포함한 전체 페이지를 캡처한다. 자동 대기(auto-waiting)가 내장돼 명시적 `sleep` 없이도 렌더링 완료 후 캡처가 잡힌다. |

대안 비교:

- **Selenium** — 드라이버(chromedriver 등)와 브라우저 버전을 따로 맞춰야 하고, 공식
  이미지에 브라우저가 번들되지 않아 컨테이너 구성이 길어진다. 전체 페이지 캡처도
  기본 제공이 아니라 스크롤·합성을 직접 구현하거나 별도 확장을 써야 한다.
- **browserless** — 브라우저를 별도 서비스로 띄우고 HTTP/WebSocket으로 붙는 방식이라
  캡처 하나 뜨자고 상시 서비스를 운영해야 한다. 이 모듈처럼 단발성 배치로 돌리는
  용도에는 구성 비용이 더 크다.

## 실행 환경

- 이미지: `mcr.microsoft.com/playwright/python:v1.62.0-noble` (고정 태그)
- 다이제스트: `sha256:aa81288e738725378becba5b3e06cb0f3a7f012a610e87e8d767a090ea3f740d`
- 이미지 크기: **3.77GB** (`docker images` 기준, arm64/linux)
- 번들 브라우저: `/ms-playwright` (`chromium-1234`, `firefox-1538`, `webkit-2336`, `ffmpeg-1011`)
- 컨테이너 파이썬: 3.12.3

### 확인된 제약: 이미지에 `playwright` 파이썬 패키지는 없다

이 태그를 실측한 결과, 이미지에는 **브라우저 바이너리만** 들어 있고 `playwright`
pip 패키지는 설치돼 있지 않다. 확인 내용:

```
$ docker run --rm mcr.microsoft.com/playwright/python:v1.62.0-noble pip show playwright
WARNING: Package(s) not found: playwright

$ docker run --rm mcr.microsoft.com/playwright/python:v1.62.0-noble env | grep -i playwright
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

따라서 실행 시 `pip install playwright==1.62.0` 한 줄이 필요하다. 다만
`PLAYWRIGHT_BROWSERS_PATH` 가 이미 설정돼 있어 **`playwright install` (브라우저
다운로드)은 필요 없다** — 번들된 브라우저를 그대로 찾아 쓴다. 이미지 태그와 pip
패키지 버전을 `1.62.0` 으로 동일하게 맞춰 버전 불일치를 방지한다.

## 실행 방법

저장소 루트에서:

```bash
docker run --rm \
  -v "$PWD":/work -w /work \
  mcr.microsoft.com/playwright/python:v1.62.0-noble \
  bash -c "pip install --quiet --root-user-action=ignore playwright==1.62.0 && python capture/capture.py"
```

- `-v "$PWD":/work` — 저장소를 컨테이너의 `/work` 에 마운트해 결과 PNG가 호스트에
  그대로 떨어지게 한다. (macOS Docker Desktop 기준 산출물은 호스트 사용자 소유로 생성됨을 확인함)
- `--rm` — 실행이 끝나면 컨테이너를 제거한다. 상태는 마운트된 파일로만 남는다.

폴백 대상만 캡처하려면 `python capture/capture.py --fallback-only` 로 바꿔 실행한다.

## 실제 실행 출력 (증거)

2026-08-05 실행 결과 원문 발췌:

```
[접속] DART 전자공시시스템 메인 -> https://dart.fss.or.kr
[성공] dart-main: HTTP 200 / title='전자공시시스템' / data/captures/20260805T003628Z_dart-main.png (410,541 bytes)
[접속] DART 공시통합검색 -> https://dart.fss.or.kr/dsab007/main.do
[성공] dart-search: HTTP 200 / title='전자공시시스템| 공시서류검색 | 공시통합검색' / data/captures/20260805T003628Z_dart-search.png (226,410 bytes)

[요약] 성공 2건 / 전체 2건, 로그: data/captures/20260805T003628Z_run.json
```

컨테이너 실행 전체 소요 시간은 `pip install` 포함 **11.8초**였다 (`time docker run ...` 실측).
이미지 pull은 최초 1회 2분 29초가 걸렸다.

검증한 내용:

- 두 페이지 모두 **HTTP 200**, 폴백 없이 1순위(DART) 대상만으로 성공했다.
- 캡처 해상도는 `dart-main` **1444x2469**, `dart-search` **1444x1252** 로,
  뷰포트 높이(900)를 넘는 전체 페이지가 잡혔다(footer까지 포함).
- 한글이 깨지지 않고 정상 렌더링됨을 PNG 육안 확인으로 검증했다. 이미지에 포함된
  폰트만으로 한글 표시가 가능했고 별도 폰트 설치는 하지 않았다.

## 산출물

| 경로 | 내용 |
| --- | --- |
| `data/captures/<UTC타임스탬프>_dart-main.png` | DART 메인 전체 페이지 |
| `data/captures/<UTC타임스탬프>_dart-search.png` | DART 공시통합검색 전체 페이지 |
| `data/captures/<UTC타임스탬프>_quotes-toscrape.png` | 폴백 대상 전체 페이지(폴백 경로 검증 시 생성) |
| `data/captures/<UTC타임스탬프>_run.json` | 실행 로그(URL, HTTP 상태, 제목, 파일 크기, 실패 사유) |

타임스탬프 형식은 `20260805T003628Z` (UTC)이며, 한 번의 실행에서 나온 파일은 같은
타임스탬프를 공유한다.

## 대상 사이트 부하 정책

- 1순위 대상은 DART 메인·공시통합검색 **2개 페이지, 각 1회씩만** 접속한다.
- 요청 사이에 `REQUEST_INTERVAL_SEC = 3.0` 초 대기를 넣었다.
- 1순위가 모두 실패할 때만 폴백 대상(`https://quotes.toscrape.com`, 크롤링 실습용
  공개 사이트)으로 전환하며, 실패 사유는 `_run.json` 의 `error` 필드에 기록된다.
  **실제 실행에서는 DART 접속이 성공해 폴백이 발동하지 않았다.**

### 폴백 경로 검증

폴백은 문서상 주장으로 남기지 않고 두 가지 방식으로 실제 실행해 확인했다.

1. `--fallback-only` 직접 실행:

```
[접속] Quotes to Scrape (크롤링 실습용 공개 사이트) -> https://quotes.toscrape.com
[성공] quotes-toscrape: HTTP 200 / title='Quotes to Scrape' / data/captures/20260805T003749Z_quotes-toscrape.png (206,910 bytes)
```

2. 1순위를 강제로 실패시켜 **자동 전환 분기**가 도는지 확인(해석 불가 도메인 주입):

```
[접속] 강제 실패 대상 -> https://dart-does-not-exist.invalid
[실패] bogus: Error: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://dart-does-not-exist.invalid/
[폴백] 1순위 대상이 모두 실패하여 폴백 대상으로 전환한다.
[성공] quotes-toscrape: HTTP 200 / title='Quotes to Scrape'
```

2번은 검증 목적의 일회성 실행이라 산출물 PNG는 저장소에 남기지 않았다.
