#!/usr/bin/env python3
"""DART 최근공시 목록 수집 스크립트.

Docker로 띄운 crawl4ai 서버(기본 http://localhost:11235)의 REST API를 호출해
DART 최근공시 목록의 지정한 페이지 범위를 헤드리스 브라우저로 렌더링한 뒤,
마크다운과 JSON 메타데이터를 data/crawl/ 아래에 저장한다.

DART 목록 화면(dsab007/main.do)은 표를 서버가 미리 심어주지 않고 페이지 로드 후
AJAX로 채운다. 그래서 그 주소를 그대로 열면 "조회 결과가 없습니다"만 렌더링된다.
페이지의 전역 함수 search()를 브라우저에서 호출하는 방법은 crawl4ai 0.9.2가
js_code를 신뢰되지 않은 요청 본문의 금지 필드로 막기 때문에 REST API로는 쓸 수 없다.
따라서 화면이 내부적으로 호출하는 것과 동일한 목록 엔드포인트
(dsab007/detailSearch.ax)를 GET으로 직접 열어 목록 HTML을 받는다.

표준 라이브러리만 사용한다. 인증 토큰은 저장소에 커밋하지 않고 환경변수
CRAWL4AI_API_TOKEN(또는 저장소 루트의 gitignore된 .env)에서 읽는다.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "crawl"

API_BASE = os.environ.get("CRAWL4AI_BASE_URL", "http://localhost:11235")
LIST_URL = (
    "https://dart.fss.or.kr/dsab007/detailSearch.ax"
    "?currentPage={page}&maxResults=15"
)

# 크롤링 윤리: 대상 서버 부하를 낮추기 위한 페이지 간 최소 대기(초).
REQUEST_INTERVAL_SEC = 2.5
PAGES = (1, 2, 3)


def load_token() -> str:
    """crawl4ai API 토큰을 환경변수 또는 .env에서 읽어 반환한다.

    :returns: Bearer 인증에 사용할 토큰 문자열
    :raises SystemExit: 토큰을 찾지 못한 경우
    """
    token = os.environ.get("CRAWL4AI_API_TOKEN")
    if token:
        return token

    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "CRAWL4AI_API_TOKEN":
                return value.strip()

    sys.exit(
        "CRAWL4AI_API_TOKEN이 없습니다. 컨테이너 기동 시 사용한 토큰을 "
        "환경변수나 .env(gitignore 대상)에 넣어주세요."
    )


def crawl_page(page: int, token: str) -> dict:
    """crawl4ai /crawl 엔드포인트로 DART 목록 한 페이지를 렌더링한다.

    :param page: DART 최근공시 목록의 페이지 번호(1부터)
    :param token: crawl4ai Bearer 토큰
    :returns: crawl4ai 응답의 results[0] 딕셔너리
    :raises RuntimeError: API가 실패를 반환한 경우
    """
    payload = {
        "urls": [LIST_URL.format(page=page)],
        "browser_config": {
            "type": "BrowserConfig",
            "params": {"headless": True},
        },
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": {
                "cache_mode": "BYPASS",
                "page_timeout": 90000,
                "delay_before_return_html": 1.0,
            },
        },
    }

    request = urllib.request.Request(
        f"{API_BASE}/crawl",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=240) as response:
        body = json.loads(response.read().decode("utf-8"))

    if not body.get("success") or not body.get("results"):
        raise RuntimeError(f"{page}페이지 크롤 실패: {body}")
    return body["results"][0]


def extract_markdown(result: dict) -> str:
    """crawl4ai 결과에서 원본 마크다운 문자열을 꺼낸다.

    :param result: crawl4ai results[0] 딕셔너리
    :returns: 마크다운 본문
    """
    markdown = result.get("markdown")
    if isinstance(markdown, dict):
        return markdown.get("raw_markdown", "")
    return markdown or ""


def summarize(result: dict, page: int, markdown: str) -> dict:
    """저장할 JSON 메타데이터를 구성한다.

    :param result: crawl4ai results[0] 딕셔너리
    :param page: 페이지 번호
    :param markdown: 추출한 마크다운 본문
    :returns: 산출물 검증에 필요한 최소 메타데이터
    """
    html = result.get("html", "") or ""
    receipt_numbers = sorted(set(re.findall(r"rcpNo=(\d{14})", html)))
    return {
        "page": page,
        "source_url": result.get("url"),
        "http_status": result.get("status_code"),
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "markdown_chars": len(markdown),
        "receipt_no_count": len(receipt_numbers),
        "receipt_no_sample": receipt_numbers[:5],
        "request_interval_sec": REQUEST_INTERVAL_SEC,
        "crawler": "crawl4ai (docker unclecode/crawl4ai:latest)",
    }


def main() -> int:
    """페이지 1~3을 순회 수집하고 결과를 저장한다.

    :returns: 프로세스 종료 코드(0 성공, 1 전체 실패)
    """
    token = load_token()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summaries: list[dict] = []
    for index, page in enumerate(PAGES):
        if index:
            # 요청 간격 준수: 첫 페이지를 제외한 매 요청 앞에서 대기한다.
            time.sleep(REQUEST_INTERVAL_SEC)

        print(f"[crawl] {page}페이지 요청 중...", flush=True)
        try:
            result = crawl_page(page, token)
        except (urllib.error.URLError, RuntimeError, TimeoutError) as error:
            print(f"[fail] {page}페이지: {error}", file=sys.stderr)
            summaries.append({"page": page, "error": str(error)})
            continue

        markdown = extract_markdown(result)
        meta = summarize(result, page, markdown)
        summaries.append(meta)

        (OUT_DIR / f"dart_page{page}.md").write_text(markdown, encoding="utf-8")
        (OUT_DIR / f"dart_page{page}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"[ok] {page}페이지 status={meta['http_status']} "
            f"공시건수={meta['receipt_no_count']} md={meta['markdown_chars']}자",
            flush=True,
        )

    (OUT_DIR / "dart_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if any("error" not in item for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
