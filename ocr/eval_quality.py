#!/usr/bin/env python3
"""OCR 결과의 한국어 인식 정확도를 정답지와 대조해 측정한다.

정답지(``ocr/reference/dart-search_labels.txt``)는 캡처된 PNG를 직접 눈으로 읽어
옮겨 적은 한국어 문자열 목록이다. 이 스크립트는 각 문자열이 OCR 결과 텍스트에
그대로 나타나는지 확인하고, 나타나지 않으면 가장 비슷한 조각을 찾아 보여준다.
"틀렸다"를 눈대중이 아니라 재현 가능한 숫자로 남기는 것이 목적이다.

공백 차이는 정확도 판단에서 제외한다(OCR이 표 레이아웃 때문에 공백을 임의로
넣거나 빼므로, 공백을 모두 제거한 뒤 비교한다).

표준 라이브러리만 사용한다.

실행 예::

    python3 ocr/eval_quality.py
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 기본 대조 쌍: (정답지, OCR 결과 텍스트)
DEFAULT_REFERENCE = REPO_ROOT / "ocr" / "reference" / "dart-search_labels.txt"
DEFAULT_OCR_TEXT = REPO_ROOT / "data" / "ocr" / "20260805T003628Z_dart-search.txt"


def load_reference(path: Path) -> list[str]:
    """정답지 파일에서 비교할 문자열 목록을 읽는다.

    Args:
        path: 정답지 텍스트 파일 경로.

    Returns:
        주석(``#``)과 빈 줄을 제외한 문자열 목록.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    return [s.strip() for s in lines if s.strip() and not s.startswith("#")]


def squeeze(text: str) -> str:
    """비교 전 공백을 모두 제거해 정규화한다.

    Args:
        text: 원본 문자열.

    Returns:
        공백류가 제거된 문자열.
    """
    return "".join(text.split())


def closest_fragment(needle: str, haystack: str) -> str:
    """OCR 결과에서 정답 문자열과 가장 비슷한 조각을 찾아 반환한다.

    Args:
        needle: 찾으려는 정답 문자열(공백 제거본).
        haystack: OCR 결과 전체(공백 제거본).

    Returns:
        가장 유사한 부분 문자열. 찾지 못하면 빈 문자열.
    """
    matcher = difflib.SequenceMatcher(None, needle, haystack)
    block = matcher.find_longest_match(0, len(needle), 0, len(haystack))
    if block.size == 0:
        return ""
    # 정답 길이만큼의 구간을 앞뒤로 넉넉히 잘라 사람이 비교하기 쉽게 만든다.
    start = max(0, block.b - block.a)
    return haystack[start : start + len(needle)]


def display_path(path: Path) -> str:
    """경로를 저장소 기준 상대 경로로 보기 좋게 만든다.

    저장소 밖 경로가 들어올 수도 있으므로 그때는 원래 경로를 그대로 돌려준다.

    Args:
        path: 표시할 경로.

    Returns:
        저장소 상대 경로 문자열, 또는 절대 경로 문자열.
    """
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def main() -> int:
    """CLI 진입점.

    Returns:
        정답지를 읽어 비교까지 마쳤으면 0.
    """
    parser = argparse.ArgumentParser(description="OCR 한국어 인식 정확도 측정")
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--ocr-text", type=Path, default=DEFAULT_OCR_TEXT)
    args = parser.parse_args()

    if not args.ocr_text.exists():
        sys.exit(f"{args.ocr_text} 가 없습니다. 먼저 OCR을 실행해주세요.")

    expected = load_reference(args.reference)
    ocr_squeezed = squeeze(args.ocr_text.read_text(encoding="utf-8"))

    hits: list[str] = []
    misses: list[tuple[str, str]] = []
    for label in expected:
        if squeeze(label) in ocr_squeezed:
            hits.append(label)
        else:
            misses.append((label, closest_fragment(squeeze(label), ocr_squeezed)))

    print(f"정답지: {display_path(args.reference)}")
    print(f"OCR   : {display_path(args.ocr_text)}")
    print(f"\n[결과] 정확 일치 {len(hits)}/{len(expected)} "
          f"({len(hits) / len(expected) * 100:.1f}%)\n")

    if misses:
        print("불일치 목록 (정답 -> OCR이 읽은 가장 가까운 조각):")
        for label, got in misses:
            print(f"  {label!r} -> {got!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
