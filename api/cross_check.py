#!/usr/bin/env python3
"""화면 크롤링으로 모은 접수번호를 DART 공식 API 응답과 대조하는 스크립트.

crawl4ai로 DART 공시통합검색 화면을 긁어 얻은 접수번호가 실제로 존재하는
공시인지, 그리고 같은 시간대에 공식 API가 돌려주는 목록과 얼마나 겹치는지를
숫자로 확인한다. 크롤링 경로를 믿어도 되는지 판단하는 근거를 만드는 것이 목적이다.

접수번호를 어디서 읽는지에 대해:
data/crawl/dart_summary.json 에는 페이지별 receipt_no_count(각 15건)와
receipt_no_sample(앞 5건)만 들어 있어 45건 전체가 없다. 전체 접수번호는
data/crawl/dart_page*.md 의 rcpNo 링크에 그대로 남아 있으므로 거기서 뽑고,
summary의 receipt_no_count 합계 및 sample과 어긋나지 않는지 교차 확인한다.

두 가지를 나눠서 본다.

1. 포함 관계. 크롤이 얻은 접수번호가 API 응답에 있는지. 크롤이 없는 공시를
   지어냈거나 접수번호를 잘못 읽었다면 여기서 드러난다.
2. API에만 있는 건의 성격. 크롤은 3페이지에서 의도적으로 멈추므로 API 쪽이
   더 많은 것은 정상이다. 다만 그 차이가 (a) 크롤 시점 이후 접수된 것인지,
   (b) 크롤이 멈춘 범위 밖의 과거 건인지, (c) 크롤이 훑은 시간 구간 안인데도
   화면 목록에 나오지 않은 건인지는 구분해야 의미가 있다.

(c)를 가려내려면 시간 순서가 필요한데 API의 rcept_dt는 날짜까지만 있고 시각이
없다. 대신 list.json 응답이 접수 시각 역순으로 정렬돼 오는 것을 실측으로
확인했으므로(서로 다른 접수번호 계열이 시간 순으로 뒤섞여 있다), 응답 순서를
시간축으로 삼는다. 이 정렬은 공식 문서에 명시된 보장이 아니라 관측된 성질이라
리포트에도 그렇게 적는다.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CRAWL_DIR = REPO_ROOT / "data" / "crawl"
API_DIR = REPO_ROOT / "data" / "api"

KST = timezone(timedelta(hours=9))
RECEIPT_PATTERN = re.compile(r"rcpNo=(\d{14})")


def load_crawl_receipts() -> tuple[set[str], dict]:
    """크롤 산출물에서 접수번호 전체와 대조용 메타데이터를 읽는다.

    :returns: (접수번호 집합, 크롤 메타데이터 딕셔너리) 튜플
    :raises SystemExit: 크롤 산출물이 없는 경우
    """
    page_files = sorted(glob.glob(str(CRAWL_DIR / "dart_page*.md")))
    if not page_files:
        sys.exit(
            f"{CRAWL_DIR.relative_to(REPO_ROOT)} 에 dart_page*.md 가 없습니다. "
            "먼저 crawler/crawl_dart.py 로 크롤을 돌려주세요."
        )

    receipts: set[str] = set()
    per_page: dict[str, int] = {}
    for path in page_files:
        found = set(RECEIPT_PATTERN.findall(Path(path).read_text(encoding="utf-8")))
        per_page[Path(path).name] = len(found)
        receipts |= found

    meta: dict = {"per_page_extracted": per_page}

    summary_path = CRAWL_DIR / "dart_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        pages = [item for item in summary if "error" not in item]
        declared = sum(int(item.get("receipt_no_count", 0)) for item in pages)
        samples = {no for item in pages for no in item.get("receipt_no_sample", [])}
        meta.update(
            {
                "summary_declared_count": declared,
                "extracted_count": len(receipts),
                "count_matches_summary": declared == len(receipts),
                "summary_samples_all_present": samples <= receipts,
                "crawl_fetched_at_utc": [
                    item.get("fetched_at_utc") for item in pages
                ],
            }
        )
    return receipts, meta


def load_api_document(date: str | None) -> dict:
    """API 수집 결과 JSON을 읽는다.

    :param date: YYYYMMDD 문자열. None이면 가장 최근 파일을 고른다.
    :returns: fetch_disclosures.py가 저장한 문서 딕셔너리
    :raises SystemExit: 파일이 없는 경우
    """
    if date:
        path = API_DIR / f"disclosures_{date}.json"
        if not path.exists():
            sys.exit(
                f"{path.relative_to(REPO_ROOT)} 가 없습니다. "
                f"먼저 python3 api/fetch_disclosures.py --date {date} 를 돌려주세요."
            )
    else:
        candidates = sorted(glob.glob(str(API_DIR / "disclosures_*.json")))
        if not candidates:
            sys.exit(
                "data/api/ 에 disclosures_*.json 이 없습니다. "
                "먼저 python3 api/fetch_disclosures.py 를 돌려주세요."
            )
        path = Path(candidates[-1])

    return json.loads(path.read_text(encoding="utf-8"))


def analyse(crawl_receipts: set[str], api_document: dict) -> dict:
    """두 집합을 대조해 리포트 본문을 만든다.

    :param crawl_receipts: 크롤로 얻은 접수번호 집합
    :param api_document: fetch_disclosures.py 산출 문서
    :returns: 리포트 딕셔너리
    """
    records = api_document.get("list") or []
    order = [row["rcept_no"] for row in records]
    position = {no: index for index, no in enumerate(order)}
    api_receipts = set(order)
    by_no = {row["rcept_no"]: row for row in records}

    matched = crawl_receipts & api_receipts
    crawl_only = sorted(crawl_receipts - api_receipts)
    match_rate = len(matched) / len(crawl_receipts) if crawl_receipts else 0.0

    report: dict = {
        "crawl_receipt_count": len(crawl_receipts),
        "api_receipt_count": len(api_receipts),
        "matched_count": len(matched),
        "match_rate_percent": round(match_rate * 100, 1),
        "crawl_only_count": len(crawl_only),
        "crawl_only": [
            {
                "rcept_no": no,
                "note": "API 응답에 없음. 접수번호 오독이거나 조회 기간이 어긋난 건.",
            }
            for no in crawl_only
        ],
        "api_only_count": len(api_receipts - crawl_receipts),
    }

    # 크롤이 훑은 시간 구간을 API 응답 순서 위에서 잡는다.
    seen = [position[no] for no in matched if no in position]
    if seen:
        newest, oldest = min(seen), max(seen)
        window = [order[i] for i in range(newest, oldest + 1)]
        missed = [no for no in window if no not in crawl_receipts]
        report["time_window"] = {
            "basis": (
                "list.json 응답이 접수 시각 역순으로 오는 것을 실측 확인해 순서를 "
                "시간축으로 사용했다. 공식 문서가 보장하는 정렬은 아니다."
            ),
            "crawl_newest_rcept_no": order[newest],
            "crawl_oldest_rcept_no": order[oldest],
            "window_size": len(window),
            "newer_than_crawl_count": newest,
            "older_than_crawl_count": len(order) - 1 - oldest,
            "missed_inside_window_count": len(missed),
            "missed_inside_window": [
                {
                    "rcept_no": no,
                    "corp_name": by_no[no].get("corp_name"),
                    "report_nm": (by_no[no].get("report_nm") or "").strip(),
                    "corp_cls": by_no[no].get("corp_cls"),
                    "rcept_dt": by_no[no].get("rcept_dt"),
                }
                for no in missed
            ],
        }

    # 접수번호 앞 8자리와 rcept_dt가 다른 건이 섞여 있어 따로 센다.
    prefix_mismatch = [
        row["rcept_no"]
        for row in records
        if row.get("rcept_dt") and row["rcept_no"][:8] != row["rcept_dt"]
    ]
    report["receipt_prefix_differs_from_rcept_dt"] = {
        "count": len(prefix_mismatch),
        "note": (
            "접수번호 앞 8자리가 rcept_dt와 다른 건. 효력발생안내처럼 전날 계열 "
            "번호를 달고 당일 공시로 잡히는 문서가 여기 해당한다."
        ),
    }
    return report


def print_report(report: dict, api_document: dict, crawl_meta: dict) -> None:
    """사람이 읽을 형태로 리포트를 출력한다.

    :param report: analyse가 만든 리포트 딕셔너리
    :param api_document: API 수집 문서
    :param crawl_meta: 크롤 메타데이터
    """
    line = "=" * 60
    print(line)
    print("  크롤링 대 공식 API 교차 검증")
    print(line)
    print(f"조회 기간      : {api_document['bgn_de']} ~ {api_document['end_de']}")
    print(f"API 수집 시각  : {api_document['fetched_at_kst']}")
    fetched = crawl_meta.get("crawl_fetched_at_utc") or []
    if fetched:
        print(f"크롤 수집 시각 : {fetched[0]} ~ {fetched[-1]} (UTC)")
    print()
    print(f"크롤 접수번호  : {report['crawl_receipt_count']}건")
    print(f"API  접수번호  : {report['api_receipt_count']}건")
    print(
        f"확인된 건      : {report['matched_count']}건 "
        f"/ 매칭률 {report['match_rate_percent']}%"
    )
    print(f"크롤에만 있음  : {report['crawl_only_count']}건")
    for item in report["crawl_only"]:
        print(f"    {item['rcept_no']}  {item['note']}")
    print(f"API에만 있음   : {report['api_only_count']}건")

    window = report.get("time_window")
    if window:
        print()
        print("-- 크롤이 훑은 시간 구간 안팎 분해 --")
        print(
            f"  크롤 구간      : {window['crawl_newest_rcept_no']} "
            f"~ {window['crawl_oldest_rcept_no']} (API 순서 기준 {window['window_size']}건)"
        )
        print(f"  크롤보다 최근  : {window['newer_than_crawl_count']}건 (크롤 종료 후 접수)")
        print(f"  크롤보다 과거  : {window['older_than_crawl_count']}건 (3페이지 제한 밖)")
        print(f"  구간 안 누락   : {window['missed_inside_window_count']}건")
        for item in window["missed_inside_window"]:
            print(
                f"    {item['rcept_no']} [{item['corp_cls']}] "
                f"{item['corp_name']} | {item['report_nm'][:44]}"
            )

    prefix = report["receipt_prefix_differs_from_rcept_dt"]
    print()
    print(f"접수번호 앞자리와 rcept_dt 불일치: {prefix['count']}건")
    print(line)


def main() -> int:
    """크롤 결과와 API 결과를 대조해 리포트를 출력하고 저장한다.

    :returns: 프로세스 종료 코드(0 성공, 1 크롤 전용 건이 있는 경우)
    """
    parser = argparse.ArgumentParser(
        description="크롤링 접수번호와 DART 공식 API 응답을 대조한다."
    )
    parser.add_argument(
        "--date",
        default=None,
        help="대조할 API 산출물 날짜(YYYYMMDD). 기본값은 data/api/ 의 최신 파일.",
    )
    args = parser.parse_args()

    crawl_receipts, crawl_meta = load_crawl_receipts()
    api_document = load_api_document(args.date)

    report = analyse(crawl_receipts, api_document)
    report["crawl_source_note"] = (
        "접수번호는 data/crawl/dart_page*.md 의 rcpNo 링크에서 뽑았다. "
        "dart_summary.json 에는 페이지별 앞 5건 표본만 있어 45건 전체가 없다."
    )
    report["crawl_meta"] = crawl_meta
    report["api_source"] = api_document.get("source")
    report["bgn_de"] = api_document.get("bgn_de")
    report["end_de"] = api_document.get("end_de")
    report["api_fetched_at_kst"] = api_document.get("fetched_at_kst")
    report["checked_at_kst"] = datetime.now(KST).isoformat()

    print_report(report, api_document, crawl_meta)

    API_DIR.mkdir(parents=True, exist_ok=True)
    out_path = API_DIR / "cross_check_report.json"
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[저장] {out_path.relative_to(REPO_ROOT)}")

    return 1 if report["crawl_only_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
