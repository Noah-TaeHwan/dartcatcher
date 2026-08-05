#!/usr/bin/env python3
"""README의 수치가 evidence·data 원본과 어긋나지 않는지 검사한다.

이 저장소의 README는 모든 주장에 근거 파일을 붙여둔 것이 강점이다. 그 강점은
문서와 근거가 같이 움직일 때만 유지되는데, 사람이 한쪽만 고치면 조용히 깨진다.
이 스크립트가 그것을 막는다.

핵심은 기대값을 이 파일에 적지 않는 것이다. 수치는 전부 원본에서 계산해내고,
계산된 값이 README에 문자열로 있는지만 확인한다. 그래서 이 스크립트가 원본과
독립적으로 틀릴 여지가 없고, 어느 한쪽만 바뀌어도 검사가 깨진다.

근거 파일이 없거나 형식이 어긋나면 통과가 아니라 실패로 끝낸다. 검사가 조용히
0건이 되는 것이 이 장치의 유일한 실패 모드이며, 이는 이 저장소가
evidence/compose_up_exitcode_trap.txt 에 기록해둔 함정과 같은 유형이다.

네트워크를 쓰지 않고 표준 라이브러리만 사용한다.
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"

# PNG 파일 시그니처. IHDR 청크에서 해상도를 읽기 전에 이것부터 확인한다.
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# 정확도 측정 출력(ocr/eval_quality.py)의 결과 줄 형식.
ACCURACY_PATTERN = re.compile(r"정확 일치 (\d+)/(\d+) \(([\d.]+)%\)")

# 크롤 마크다운에 남은 공시 원문 링크의 접수번호.
RECEIPT_PATTERN = re.compile(r"rcpNo=(\d+)")


class CheckError(RuntimeError):
    """근거 파일이 없거나 형식이 어긋나 수치를 파생할 수 없는 경우의 예외."""


def read_evidence(relative: str) -> str:
    """근거 파일을 읽어 본문을 돌려준다.

    :param relative: 저장소 루트 기준 상대 경로
    :returns: 파일 본문 문자열
    :raises CheckError: 파일이 없는 경우
    """
    path = REPO_ROOT / relative
    if not path.exists():
        raise CheckError(f"근거 파일이 없습니다: {relative}")
    return path.read_text(encoding="utf-8")


def derive_accuracy(relative: str) -> str:
    """정확도 측정 출력에서 백분율을 파생한다.

    적힌 백분율을 그대로 믿지 않고 분자·분모로 다시 계산해 대조한다. 근거 파일
    자체가 앞뒤가 안 맞는 경우를 잡기 위해서다.

    :param relative: 정확도 출력 파일의 상대 경로
    :returns: "61.3%" 형태의 문자열
    :raises CheckError: 형식을 찾지 못하거나 재계산 값이 다른 경우
    """
    text = read_evidence(relative)
    match = ACCURACY_PATTERN.search(text)
    if not match:
        raise CheckError(
            f"{relative} 에서 '정확 일치 N/M (P%)' 형식을 찾지 못했습니다."
        )
    hit, total, printed = int(match.group(1)), int(match.group(2)), match.group(3)
    if total == 0:
        raise CheckError(f"{relative} 의 분모가 0입니다.")
    recomputed = f"{round(hit / total * 100, 1):.1f}"
    if recomputed != printed:
        raise CheckError(
            f"{relative} 의 {hit}/{total} 은 {recomputed}% 인데 {printed}% 로 적혀 있습니다."
        )
    return f"{printed}%"


def derive_png(relative: str) -> tuple[str, str]:
    """PNG의 해상도와 파일 크기를 파생한다.

    해상도는 IHDR 청크에서 직접 읽는다. 이미지 라이브러리를 쓰지 않는 이유는
    표준 라이브러리만 쓰기로 한 제약 때문이다.

    :param relative: PNG 파일의 상대 경로
    :returns: ("1444×2469", "410,541") 형태의 튜플
    :raises CheckError: 파일이 없거나 PNG가 아닌 경우
    """
    path = REPO_ROOT / relative
    if not path.exists():
        raise CheckError(f"캡처 파일이 없습니다: {relative}")
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != PNG_SIGNATURE:
        raise CheckError(f"PNG 시그니처가 아닙니다: {relative}")
    width, height = struct.unpack(">II", header[16:24])
    return f"{width}×{height}", f"{path.stat().st_size:,}"


def derive_receipt_count() -> str:
    """크롤 산출물에서 유니크 접수번호 개수를 파생한다.

    페이지별로 세지 않고 전체를 집합으로 합친다. README가 "페이지 간 중복 0"을
    함께 주장하므로, 중복이 생기면 개수가 줄어 검사가 깨진다.

    :returns: "45건" 형태의 문자열
    :raises CheckError: 크롤 마크다운이 하나도 없는 경우
    """
    pages = sorted((REPO_ROOT / "data" / "crawl").glob("dart_page*.md"))
    if not pages:
        raise CheckError("data/crawl/dart_page*.md 가 하나도 없습니다.")
    receipts: set[str] = set()
    for page in pages:
        receipts |= set(RECEIPT_PATTERN.findall(page.read_text(encoding="utf-8")))
    if not receipts:
        raise CheckError("크롤 마크다운에서 접수번호를 하나도 찾지 못했습니다.")
    return f"{len(receipts)}건"


def derive_output_count() -> str:
    """저장소에 남긴 캡처·OCR 산출물 개수를 파생한다.

    README가 "5개씩"이라고 적으므로 두 디렉터리의 개수가 같아야 그 표현이
    성립한다. 다르면 문장 자체가 틀린 것이므로 실패로 처리한다.

    :returns: "5개씩" 형태의 문자열
    :raises CheckError: 어느 한쪽이 비었거나 개수가 다른 경우
    """
    captures = list((REPO_ROOT / "data" / "captures").glob("*.png"))
    texts = list((REPO_ROOT / "data" / "ocr").glob("*.txt"))
    if not captures or not texts:
        raise CheckError("data/captures/*.png 또는 data/ocr/*.txt 가 비어 있습니다.")
    if len(captures) != len(texts):
        raise CheckError(
            f"캡처 {len(captures)}개와 OCR {len(texts)}개가 다릅니다. "
            f"README의 'N개씩' 표현이 성립하지 않습니다."
        )
    return f"{len(captures)}개씩"


def build_checks() -> list[tuple[str, str]]:
    """(검사 이름, README에 있어야 할 문자열) 목록을 만든다.

    :returns: 검사 튜플 리스트
    :raises CheckError: 어느 하나라도 파생에 실패한 경우
    """
    main_res, main_size = derive_png("data/captures/20260805T003628Z_dart-main.png")
    search_res, search_size = derive_png(
        "data/captures/20260805T003628Z_dart-search.png"
    )
    return [
        ("OCR 한국어 정확도", derive_accuracy("evidence/ocr_quality.txt")),
        (
            "HiDPI 재측정 정확도",
            derive_accuracy("evidence/ocr_quality_hidpi_experiment.txt"),
        ),
        ("캡처 해상도(main)", main_res),
        ("캡처 크기(main)", main_size),
        ("캡처 해상도(search)", search_res),
        ("캡처 크기(search)", search_size),
        ("크롤 유니크 접수번호", derive_receipt_count()),
        ("산출물 개수", derive_output_count()),
    ]


def main() -> int:
    """근거에서 파생한 수치가 README에 있는지 확인한다.

    :returns: 프로세스 종료 코드(0 통과, 1 실패)
    """
    if not README_PATH.exists():
        print("[실패] README.md 가 없습니다.", file=sys.stderr)
        return 1

    try:
        checks = build_checks()
    except CheckError as error:
        print(f"[실패] 근거에서 수치를 파생하지 못했습니다: {error}", file=sys.stderr)
        return 1

    readme = README_PATH.read_text(encoding="utf-8")
    failures: list[tuple[str, str]] = []

    print(f"근거 대조 {len(checks)}건")
    for name, derived in checks:
        found = derived in readme
        mark = "ok  " if found else "FAIL"
        print(f"  [{mark}] {name}: {derived}")
        if not found:
            failures.append((name, derived))

    if failures:
        # 표준출력이 파이프·파일로 리다이렉트되면 블록 버퍼링되어 표준에러보다
        # 늦게 화면에 나타난다. 위에서 출력한 검사 목록이 실패 요약보다
        # 먼저 보이도록 첫 표준에러 출력 전에 명시적으로 비운다.
        sys.stdout.flush()
        print("", file=sys.stderr)
        print(
            f"[실패] 근거에서 파생한 값이 README에 없습니다({len(failures)}건).",
            file=sys.stderr,
        )
        for name, derived in failures:
            print(f"  {name}: README에 '{derived}' 가 있어야 합니다.", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "근거 파일을 바꿨다면 README의 해당 수치도 같이 고쳐야 합니다.",
            file=sys.stderr,
        )
        return 1

    print(f"\n[통과] {len(checks)}건 전부 README와 일치합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
