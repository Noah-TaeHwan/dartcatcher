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

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from robots_check import check_urls_allowed

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "crawl"
DEFAULT_CONFIG = REPO_ROOT / "crawler" / "sites.json"

API_BASE = os.environ.get("CRAWL4AI_BASE_URL", "http://localhost:11235")


def load_site(config_path: Path, site_name: str) -> dict:
    """설정 파일에서 대상 사이트 구성을 읽어 반환한다.

    :param config_path: 대상 URL 설정이 담긴 JSON 파일 경로
    :param site_name: 불러올 사이트 키
    :returns: 그 사이트의 구성 딕셔너리
    :raises SystemExit: 설정 파일이 없거나 사이트 키가 없는 경우
    """
    if not config_path.exists():
        sys.exit(f"설정 파일이 없습니다: {config_path}")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    sites = data.get("sites", {})
    if site_name not in sites:
        sys.exit(f"설정 파일에 '{site_name}' 사이트가 없습니다.")
    return sites[site_name]


def build_page_urls(template: str, pages: list[int]) -> list[str]:
    """목록 URL 템플릿에 페이지 번호를 채워 대상 URL 목록을 만든다.

    :param template: `{page}` 자리표를 가진 URL 템플릿
    :param pages: 크롤할 페이지 번호 목록
    :returns: 채워진 URL 목록
    """
    return [template.format(page=page) for page in pages]


def verify_robots(site: dict, urls: list[str]) -> None:
    """robots.txt 규칙으로 대상 URL을 검사하고 금지되면 중단한다.

    :param site: 대상 사이트 구성(robots_source, user_agent 포함)
    :param urls: robots.txt에 대조할 대상 URL 목록
    :raises SystemExit: 금지된 URL이 하나라도 있는 경우
    """
    denied = check_urls_allowed(
        site["robots_source"],
        site["user_agent"],
        urls,
        REPO_ROOT,
    )
    if denied:
        blocked = "\n  ".join(denied)
        sys.exit(
            "robots.txt가 다음 URL을 금지해 중단합니다.\n"
            f"  {blocked}\n"
            "robots_source(기본 evidence/dart_robots.txt)를 확인하세요."
        )
    print(f"[robots] {site['label']} 대상 URL {len(urls)}건 전부 허용 확인됨")


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


def crawl_page(page: int, token: str, site: dict) -> dict:
    """crawl4ai /crawl 엔드포인트로 대상 목록 한 페이지를 렌더링한다.

    :param page: 대상 목록의 페이지 번호(1부터)
    :param token: crawl4ai Bearer 토큰
    :param site: 대상 사이트 구성(list_url_template, page_timeout, delay 포함)
    :returns: crawl4ai 응답의 results[0] 딕셔너리
    :raises RuntimeError: API가 실패를 반환한 경우
    """
    payload = {
        "urls": [site["list_url_template"].format(page=page)],
        "browser_config": {
            "type": "BrowserConfig",
            "params": {"headless": True},
        },
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": {
                "cache_mode": "BYPASS",
                "page_timeout": site["page_timeout"],
                "delay_before_return_html": site["delay_before_return_html"],
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


def summarize(result: dict, page: int, markdown: str, interval: float) -> dict:
    """저장할 JSON 메타데이터를 구성한다.

    :param result: crawl4ai results[0] 딕셔너리
    :param page: 페이지 번호
    :param markdown: 추출한 마크다운 본문
    :param interval: 요청 간격(초). 메타데이터에 그대로 기록한다
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
        "request_interval_sec": interval,
        "crawler": "crawl4ai (docker unclecode/crawl4ai:latest)",
    }


def parse_args() -> argparse.Namespace:
    """명령줄 인자를 해석한다.

    :returns: 해석된 인자 네임스페이스
    """
    parser = argparse.ArgumentParser(description="대상 사이트 목록 수집")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="대상 URL 설정 JSON 파일 (기본 crawler/sites.json)",
    )
    parser.add_argument(
        "--site",
        default="dart",
        help="설정 파일에서 불러올 사이트 키 (기본 dart)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="robots.txt 검사까지만 하고 크롤링 없이 종료",
    )
    return parser.parse_args()


def main() -> int:
    """구성한 사이트의 페이지를 순회 수집하고 결과를 저장한다.

    1) 설정 파일에서 대상 사이트를 읽는다. 2) robots.txt로 대상 URL이
    전부 허용되는지 확인하고 금지되면 중단한다. 3) 허용되면 페이지별로
    수집·저장하고 요약을 남긴다.

    :returns: 프로세스 종료 코드(0 성공, 1 전체 실패)
    """
    args = parse_args()
    site = load_site(args.config, args.site)
    pages = site["pages"]
    interval = site["request_interval_sec"]

    urls = build_page_urls(site["list_url_template"], pages)
    verify_robots(site, urls)
    if args.check_only:
        return 0

    token = load_token()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    prefix = args.site
    summaries: list[dict] = []
    for index, page in enumerate(pages):
        if index:
            # 요청 간격 준수: 첫 페이지를 제외한 매 요청 앞에서 대기한다.
            time.sleep(interval)

        print(f"[crawl] {page}페이지 요청 중...", flush=True)
        try:
            result = crawl_page(page, token, site)
        except (urllib.error.URLError, RuntimeError, TimeoutError) as error:
            print(f"[fail] {page}페이지: {error}", file=sys.stderr)
            summaries.append({"page": page, "error": str(error)})
            continue

        markdown = extract_markdown(result)
        meta = summarize(result, page, markdown, interval)
        summaries.append(meta)

        (OUT_DIR / f"{prefix}_page{page}.md").write_text(markdown, encoding="utf-8")
        (OUT_DIR / f"{prefix}_page{page}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"[ok] {page}페이지 status={meta['http_status']} "
            f"공시건수={meta['receipt_no_count']} md={meta['markdown_chars']}자",
            flush=True,
        )

    (OUT_DIR / f"{prefix}_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if any("error" not in item for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
