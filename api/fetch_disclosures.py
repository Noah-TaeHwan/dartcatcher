#!/usr/bin/env python3
"""DART 공식 OpenAPI(list.json)로 공시 목록을 받아 저장하는 스크립트.

이 저장소의 다른 수집 경로(crawl4ai 화면 크롤링)와 달리, 금융감독원이 직접
제공하는 공시검색 API를 호출한다. HTML을 파싱하지 않고 JSON을 그대로 받으므로
화면 구조가 바뀌어도 깨지지 않는다.

기본 동작은 오늘(Asia/Seoul) 하루치 공시 목록 전체를 받아
data/api/disclosures_YYYYMMDD.json 에 저장하는 것이다.

한 번의 응답은 page_count 로 지정한 건수까지만 담기고 나머지는 total_page 로
나뉘어 온다. 하루치라도 100건을 넘는 날이 흔해서(실측 2026-08-05 = 259건)
total_page 만큼 page_no 를 올려가며 전부 받는다. 한 페이지만 받으면 그날
공시의 일부만 손에 들어와, 크롤링 결과와 대조할 때 없는 것을 없다고 잘못
판단하게 된다.

인증키는 환경변수 API_K_DART 에서만 읽는다. 저장소나 .env 에 쓰지 않으며,
로그로 찍는 URL에서도 키 자리는 가린다.

전체 목록 조회이므로 corp_code 는 넘기지 않는다. 따라서 고유번호 매핑 파일
(corpCode.xml)도 받을 필요가 없다. 대신 스펙상 bgn_de ~ end_de 는 3개월을
넘길 수 없으므로 호출 전에 검사한다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "api"

API_URL = "https://opendart.fss.or.kr/api/list.json"
KST = timezone(timedelta(hours=9))

# 한 번의 요청으로 받을 최대 건수. 스펙상 상한이 100이다.
PAGE_COUNT = 100
# 페이지를 이어 받을 때의 최소 대기(초). 공식 API지만 연속 호출을 몰아치지 않는다.
REQUEST_INTERVAL_SEC = 0.3
# 스펙상 bgn_de ~ end_de 최대 간격(일). 3개월을 넉넉히 잡은 값이다.
MAX_RANGE_DAYS = 92
# 폭주 방지용 페이지 상한. 하루치 조회에서는 닿을 일이 없다.
MAX_PAGES = 50

# status 필드가 000이 아닐 때 사람이 읽을 수 있게 옮긴 표.
# 값은 DART 개발가이드의 상태코드 설명을 그대로 따른다.
STATUS_MESSAGES = {
    "000": "정상",
    "010": "등록되지 않은 키입니다. 발급받은 인증키가 맞는지 확인하세요.",
    "011": "사용할 수 없는 키입니다. 일시적으로 사용이 중지된 상태입니다.",
    "012": "접근할 수 없는 IP입니다.",
    "013": "조회된 데이터가 없습니다. 조회 기간에 접수된 공시가 없을 수 있습니다.",
    "014": "파일이 존재하지 않습니다.",
    "020": "요청 제한을 초과했습니다. 인증키당 일일 호출 한도를 넘긴 상태입니다.",
    "021": "조회 가능한 회사 개수가 초과했습니다. 최대 100건입니다.",
    "100": "필드의 부적절한 값입니다. 날짜 형식(YYYYMMDD)과 값의 범위를 확인하세요.",
    "101": "부적절한 접근입니다.",
    "800": "시스템 점검으로 서비스가 중지 중입니다.",
    "900": "정의되지 않은 오류가 발생했습니다.",
    "901": "인증키의 개인정보 보유기간이 만료되어 사용할 수 없습니다.",
}


class DartApiError(RuntimeError):
    """DART API가 status 000 이외의 코드를 돌려준 경우의 예외."""

    def __init__(self, status: str, message: str) -> None:
        """상태코드와 API가 준 메시지를 담아 예외를 만든다.

        :param status: DART가 응답한 status 코드 문자열
        :param message: DART가 응답한 message 문자열
        """
        self.status = status
        self.message = message
        known = STATUS_MESSAGES.get(status, "상태코드표에 없는 코드입니다.")
        super().__init__(f"[status={status}] {known} (API 메시지: {message})")


def load_api_key() -> str:
    """DART 인증키를 환경변수에서 읽어 반환한다.

    키는 환경변수에서만 읽는다. .env 를 포함해 저장소 안 어디에도 두지 않는다.

    :returns: 40자리 인증키 문자열
    :raises SystemExit: 환경변수가 없거나 길이가 40자가 아닌 경우
    """
    key = os.environ.get("API_K_DART", "").strip()
    if not key:
        sys.exit(
            "API_K_DART 환경변수가 없습니다. "
            "https://opendart.fss.or.kr 에서 인증키를 발급받아 셸 환경변수로 넣어주세요."
        )
    if len(key) != 40:
        sys.exit(
            f"API_K_DART 길이가 {len(key)}자입니다. DART 인증키는 40자입니다. "
            "값을 다시 확인해주세요."
        )
    return key


def masked_url(params: dict) -> str:
    """인증키를 가린 요청 URL을 만든다. 로그와 산출물에는 이 형태만 남긴다.

    :param params: 요청 쿼리 파라미터 딕셔너리
    :returns: crtfc_key 값이 가려진 URL 문자열
    """
    rest = {key: value for key, value in params.items() if key != "crtfc_key"}
    query = urllib.parse.urlencode(rest)
    if "crtfc_key" not in params:
        return f"{API_URL}?{query}"
    return f"{API_URL}?crtfc_key=***&{query}"


def check_date_range(bgn_de: str, end_de: str) -> None:
    """조회 기간이 형식과 3개월 제한을 지키는지 확인한다.

    :param bgn_de: 시작일 YYYYMMDD
    :param end_de: 종료일 YYYYMMDD
    :raises SystemExit: 형식이 어긋나거나 기간이 뒤집혔거나 3개월을 넘는 경우
    """
    try:
        begin = datetime.strptime(bgn_de, "%Y%m%d")
        end = datetime.strptime(end_de, "%Y%m%d")
    except ValueError:
        sys.exit(f"날짜는 YYYYMMDD 형식이어야 합니다. (bgn_de={bgn_de}, end_de={end_de})")

    if begin > end:
        sys.exit(f"시작일이 종료일보다 늦습니다. (bgn_de={bgn_de}, end_de={end_de})")

    span = (end - begin).days
    if span > MAX_RANGE_DAYS:
        sys.exit(
            f"조회 기간이 {span}일입니다. DART 공시검색은 한 번에 3개월까지만 "
            f"조회할 수 있으므로 기간을 나눠서 호출하세요."
        )


def fetch_page(key: str, bgn_de: str, end_de: str, page_no: int) -> dict:
    """공시검색 API를 한 페이지 호출해 파싱한 응답을 반환한다.

    :param key: DART 인증키
    :param bgn_de: 시작일 YYYYMMDD
    :param end_de: 종료일 YYYYMMDD
    :param page_no: 페이지 번호(1부터)
    :returns: 파싱한 응답 딕셔너리
    :raises DartApiError: status가 000이 아닌 경우
    :raises SystemExit: 네트워크 오류나 JSON 파싱 실패
    """
    params = {
        "crtfc_key": key,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_no": page_no,
        "page_count": PAGE_COUNT,
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # 오류 메시지에 원본 URL이 섞여 키가 새지 않도록 마스킹한 주소만 남긴다.
        sys.exit(f"HTTP {error.code} 응답: {masked_url(params)}")
    except (urllib.error.URLError, TimeoutError) as error:
        sys.exit(f"요청 실패({error}): {masked_url(params)}")
    except json.JSONDecodeError:
        sys.exit(f"JSON으로 파싱할 수 없는 응답: {masked_url(params)}")

    status = str(body.get("status", ""))
    if status != "000":
        raise DartApiError(status, str(body.get("message", "")))
    return body


def fetch_all(key: str, bgn_de: str, end_de: str) -> tuple[list[dict], dict]:
    """total_page 만큼 순회하며 기간 내 공시를 전부 받는다.

    :param key: DART 인증키
    :param bgn_de: 시작일 YYYYMMDD
    :param end_de: 종료일 YYYYMMDD
    :returns: (공시 레코드 리스트, 첫 페이지 응답의 메타 정보) 튜플
    """
    first = fetch_page(key, bgn_de, end_de, 1)
    total_page = int(first.get("total_page", 1))
    total_count = int(first.get("total_count", 0))
    records: list[dict] = list(first.get("list") or [])
    print(
        f"[ok] 1/{total_page}페이지 {len(records)}건 (기간 전체 {total_count}건)",
        flush=True,
    )

    if total_page > MAX_PAGES:
        print(
            f"[주의] total_page가 {total_page}입니다. 상한 {MAX_PAGES}페이지까지만 받습니다.",
            file=sys.stderr,
        )
        total_page = MAX_PAGES

    for page_no in range(2, total_page + 1):
        time.sleep(REQUEST_INTERVAL_SEC)
        page = fetch_page(key, bgn_de, end_de, page_no)
        rows = list(page.get("list") or [])
        records.extend(rows)
        print(f"[ok] {page_no}/{total_page}페이지 {len(rows)}건", flush=True)

    meta = {
        "total_count": total_count,
        "total_page": int(first.get("total_page", 1)),
        "pages_fetched": min(total_page, MAX_PAGES),
    }
    return records, meta


def build_document(
    records: list[dict], meta: dict, bgn_de: str, end_de: str
) -> dict:
    """저장할 JSON 문서를 구성한다.

    :param records: 수집한 공시 레코드 리스트
    :param meta: fetch_all이 돌려준 메타 정보
    :param bgn_de: 시작일 YYYYMMDD
    :param end_de: 종료일 YYYYMMDD
    :returns: 파일로 쓸 딕셔너리
    """
    receipt_numbers = sorted({row["rcept_no"] for row in records if row.get("rcept_no")})
    return {
        "source": "DART OPEN API (list.json)",
        "request_url": masked_url(
            {
                "crtfc_key": "",
                "bgn_de": bgn_de,
                "end_de": end_de,
                "page_no": 1,
                "page_count": PAGE_COUNT,
            }
        ),
        "bgn_de": bgn_de,
        "end_de": end_de,
        "fetched_at_kst": datetime.now(KST).isoformat(),
        "total_count": meta["total_count"],
        "total_page": meta["total_page"],
        "pages_fetched": meta["pages_fetched"],
        "record_count": len(records),
        "unique_receipt_no_count": len(receipt_numbers),
        "list": records,
    }


def main() -> int:
    """인자를 읽어 하루치(또는 지정 기간) 공시를 받아 저장한다.

    :returns: 프로세스 종료 코드(0 성공, 1 실패)
    """
    today_kst = datetime.now(KST).strftime("%Y%m%d")
    parser = argparse.ArgumentParser(
        description="DART 공식 OpenAPI로 공시 목록을 받아 data/api/ 에 저장한다."
    )
    parser.add_argument(
        "--date",
        default=None,
        help="하루치를 받을 날짜(YYYYMMDD). 기본값은 오늘(Asia/Seoul).",
    )
    parser.add_argument("--bgn-de", default=None, help="시작일 YYYYMMDD")
    parser.add_argument("--end-de", default=None, help="종료일 YYYYMMDD")
    args = parser.parse_args()

    if args.bgn_de or args.end_de:
        bgn_de = args.bgn_de or args.end_de
        end_de = args.end_de or args.bgn_de
    else:
        bgn_de = end_de = args.date or today_kst

    check_date_range(bgn_de, end_de)
    key = load_api_key()

    print(f"[요청] {masked_url({'crtfc_key': '', 'bgn_de': bgn_de, 'end_de': end_de, 'page_count': PAGE_COUNT})}", flush=True)

    try:
        records, meta = fetch_all(key, bgn_de, end_de)
    except DartApiError as error:
        print(f"[실패] {error}", file=sys.stderr)
        return 1

    document = build_document(records, meta, bgn_de, end_de)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"disclosures_{end_de}.json"
    out_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"[저장] {out_path.relative_to(REPO_ROOT)} "
        f"{document['record_count']}건 "
        f"(접수번호 유니크 {document['unique_receipt_no_count']}건)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
