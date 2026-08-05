"""DART 공시 사이트 전체 페이지 스크린샷 캡처 스크립트.

Microsoft 공식 Playwright 파이썬 이미지
(``mcr.microsoft.com/playwright/python``) 안에서 실행하는 것을 전제로 한다.
Chromium 브라우저와 시스템 의존성이 이미지에 포함돼 있어 별도 설치 없이
컨테이너 안에서 바로 헤드리스 브라우저를 띄울 수 있다.

동작 개요:
    1. 1순위 대상(DART)에 순서대로 접속을 시도한다.
    2. 접속에 성공하면 전체 페이지 스크린샷을 ``data/captures/`` 에 PNG로 저장한다.
    3. 1순위 대상이 모두 실패하면 폴백 대상(quotes.toscrape.com)으로 전환하고,
       실패 사유를 실행 로그(JSON)에 남긴다.

과도한 요청 금지 원칙에 따라 대상 URL은 각각 1회씩만 접속하며,
요청 사이에는 ``REQUEST_INTERVAL_SEC`` 만큼 대기한다.

실행 예:
    python capture/capture.py
    python capture/capture.py --fallback-only   # 폴백 대상만 캡처
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

# 저장소 루트 기준 경로. 컨테이너에서는 /work 가 저장소 루트로 마운트된다.
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "captures"

# 요청 간 최소 대기 시간(초). 대상 서버에 부담을 주지 않기 위한 값.
REQUEST_INTERVAL_SEC = 3.0

# 페이지 로딩 타임아웃(밀리초).
NAVIGATION_TIMEOUT_MS = 30_000

# 렌더링 안정화를 위해 로딩 완료 후 추가로 기다리는 시간(밀리초).
SETTLE_TIMEOUT_MS = 3_000

# 브라우저 뷰포트 크기. 전체 페이지 캡처이므로 세로는 시작 높이일 뿐이다.
VIEWPORT = {"width": 1440, "height": 900}

# 일반 브라우저와 동일한 User-Agent 를 사용해 헤드리스 차단을 줄인다.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class Target:
    """캡처 대상 한 건을 나타내는 값 객체.

    Attributes:
        slug: 파일 이름에 쓰이는 짧은 식별자.
        url: 접속할 URL.
        description: 사람이 읽는 대상 설명.
    """

    slug: str
    url: str
    description: str


# 1순위 대상: 전자공시시스템(DART). 메인 + 공시검색 두 페이지만 접속한다.
PRIMARY_TARGETS: tuple[Target, ...] = (
    Target("dart-main", "https://dart.fss.or.kr", "DART 전자공시시스템 메인"),
    Target(
        "dart-search",
        "https://dart.fss.or.kr/dsab007/main.do",
        "DART 공시통합검색",
    ),
)

# 폴백 대상: 크롤링 학습용으로 공개된 정적 사이트.
FALLBACK_TARGETS: tuple[Target, ...] = (
    Target(
        "quotes-toscrape",
        "https://quotes.toscrape.com",
        "Quotes to Scrape (크롤링 실습용 공개 사이트)",
    ),
)


@dataclass
class CaptureResult:
    """캡처 시도 1건의 결과.

    Attributes:
        slug: 대상 식별자.
        url: 접속한 URL.
        ok: 스크린샷 저장까지 성공했는지 여부.
        status: HTTP 응답 상태 코드(없으면 None).
        title: 페이지 ``<title>`` 값.
        screenshot: 저장된 PNG의 저장소 상대 경로.
        bytes: 저장된 PNG 파일 크기(바이트).
        error: 실패 사유(성공 시 None).
    """

    slug: str
    url: str
    ok: bool
    status: int | None = None
    title: str | None = None
    screenshot: str | None = None
    bytes: int | None = None
    error: str | None = None


def _timestamp() -> str:
    """파일명에 쓸 UTC 타임스탬프 문자열을 반환한다.

    Returns:
        ``20260805T093000Z`` 형태의 문자열.
    """
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def capture_one(page, target: Target, stamp: str) -> CaptureResult:
    """대상 페이지 1건을 접속해 전체 페이지 스크린샷을 저장한다.

    Args:
        page: Playwright ``Page`` 객체.
        target: 캡처 대상.
        stamp: 이번 실행의 공통 타임스탬프(파일명에 사용).

    Returns:
        성공/실패 정보가 담긴 ``CaptureResult``.
    """
    print(f"[접속] {target.description} -> {target.url}", flush=True)
    try:
        response = page.goto(
            target.url,
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT_MS,
        )
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        reason = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
        print(f"[실패] {target.slug}: {reason}", flush=True)
        return CaptureResult(target.slug, target.url, ok=False, error=reason)

    status = response.status if response is not None else None
    if status is not None and status >= 400:
        reason = f"HTTP {status} 응답"
        print(f"[실패] {target.slug}: {reason}", flush=True)
        return CaptureResult(
            target.slug, target.url, ok=False, status=status, error=reason
        )

    # 네트워크가 완전히 조용해지지 않는 사이트가 있으므로 실패해도 진행한다.
    try:
        page.wait_for_load_state("networkidle", timeout=SETTLE_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        print(f"[안내] {target.slug}: networkidle 미도달, 현재 상태로 캡처", flush=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{stamp}_{target.slug}.png"
    page.screenshot(path=str(out_path), full_page=True)

    size = out_path.stat().st_size
    rel = out_path.relative_to(REPO_ROOT).as_posix()
    print(
        f"[성공] {target.slug}: HTTP {status} / title={page.title()!r} "
        f"/ {rel} ({size:,} bytes)",
        flush=True,
    )
    return CaptureResult(
        slug=target.slug,
        url=target.url,
        ok=True,
        status=status,
        title=page.title(),
        screenshot=rel,
        bytes=size,
    )


def run(
    targets: list[Target], fallback: list[Target], stamp: str
) -> list[CaptureResult]:
    """대상 목록을 순회하며 캡처하고, 전부 실패하면 폴백으로 전환한다.

    Args:
        targets: 1순위 캡처 대상 목록.
        fallback: 1순위가 모두 실패했을 때 사용할 폴백 대상 목록.
        stamp: 이번 실행의 공통 타임스탬프.

    Returns:
        1순위 결과와(필요 시) 폴백 결과를 합친 목록.
    """
    results: list[CaptureResult] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        context = browser.new_context(viewport=VIEWPORT, user_agent=USER_AGENT)
        page = context.new_page()

        for index, target in enumerate(targets):
            if index > 0:
                sleep(REQUEST_INTERVAL_SEC)  # 과도한 요청 방지
            results.append(capture_one(page, target, stamp))

        if targets and not any(r.ok for r in results):
            print(
                "[폴백] 1순위 대상이 모두 실패하여 폴백 대상으로 전환한다.",
                flush=True,
            )
            for target in fallback:
                sleep(REQUEST_INTERVAL_SEC)
                results.append(capture_one(page, target, stamp))

        context.close()
        browser.close()

    return results


def write_log(results: list[CaptureResult], stamp: str) -> Path:
    """실행 결과를 JSON 로그 파일로 남긴다.

    Args:
        results: 캡처 결과 목록.
        stamp: 실행 타임스탬프.

    Returns:
        기록한 로그 파일 경로.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUT_DIR / f"{stamp}_run.json"
    payload = {
        "captured_at_utc": stamp,
        "image": "mcr.microsoft.com/playwright/python:v1.62.0-noble",
        "results": [asdict(r) for r in results],
    }
    log_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return log_path


def main() -> int:
    """CLI 진입점.

    Returns:
        성공한 캡처가 하나라도 있으면 0, 전부 실패하면 1.
    """
    parser = argparse.ArgumentParser(description="Playwright 전체 페이지 캡처")
    parser.add_argument(
        "--fallback-only",
        action="store_true",
        help="1순위(DART)를 건너뛰고 폴백 대상만 캡처한다",
    )
    args = parser.parse_args()

    stamp = _timestamp()
    if args.fallback_only:
        # 폴백 대상을 1순위 자리에 넣어 그대로 캡처한다(추가 폴백 없음).
        results = run(list(FALLBACK_TARGETS), [], stamp)
    else:
        results = run(list(PRIMARY_TARGETS), list(FALLBACK_TARGETS), stamp)

    log_path = write_log(results, stamp)
    ok_count = sum(1 for r in results if r.ok)
    print(
        f"\n[요약] 성공 {ok_count}건 / 전체 {len(results)}건, "
        f"로그: {log_path.relative_to(REPO_ROOT).as_posix()}",
        flush=True,
    )
    return 0 if ok_count else 1


if __name__ == "__main__":
    sys.exit(main())
