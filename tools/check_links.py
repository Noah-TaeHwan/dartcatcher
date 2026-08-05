#!/usr/bin/env python3
"""README 5종의 상대 링크와 목차 앵커가 실제로 가리키는 대상이 있는지 검사한다.

이 저장소는 문서가 서로를 많이 참조한다. 루트 README가 모듈 README와 evidence
파일을 가리키고, 목차가 본문 헤딩을 가리킨다. 파일을 옮기거나 헤딩 문구를 바꾸면
조용히 끊어지는데 GitHub은 아무 경고도 주지 않는다.

코드 펜스 안쪽은 건너뛴다. 루트 README의 크롤 결과 발췌에 (...) 로 줄인 링크가
들어 있어 그대로 검사하면 오탐이 난다. 예시일 뿐 실제 링크가 아니다.

네트워크를 쓰지 않는다. 외부 URL은 검사 대상이 아니다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 검사 대상 문서. 루트와 모듈 README 넷.
TARGET_DOCS = [
    "README.md",
    "crawler/README.md",
    "capture/README.md",
    "ocr/README.md",
    "api/README.md",
]

LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")

# 앵커 슬러그를 만들 때 지우는 문자. GitHub은 문장부호를 버리고 공백을 -로 바꾼다.
ANCHOR_STRIP = re.compile(r"[^\w\s\-가-힣]", re.UNICODE)


def strip_code_fences(text: str) -> str:
    """코드 펜스 내부를 빈 줄로 바꿔 검사 대상에서 제외한다.

    줄 번호를 유지하려고 삭제 대신 빈 줄로 치환한다.

    :param text: 마크다운 원문
    :returns: 펜스 내부가 비워진 문자열
    """
    lines = text.split("\n")
    result: list[str] = []
    inside = False
    for line in lines:
        if FENCE_PATTERN.match(line):
            inside = not inside
            result.append("")
            continue
        result.append("" if inside else line)
    return "\n".join(result)


def anchor_slug(heading: str) -> str:
    """헤딩 문구를 GitHub 앵커 슬러그로 바꾼다.

    :param heading: `#` 을 제거한 헤딩 문구
    :returns: 앵커 슬러그 문자열
    """
    slug = heading.strip().lower()
    slug = ANCHOR_STRIP.sub("", slug)
    return slug.replace(" ", "-")


def check_document(relative: str) -> list[str]:
    """문서 하나의 상대 링크와 앵커를 검사한다.

    :param relative: 저장소 루트 기준 문서 경로
    :returns: 문제 설명 문자열 리스트. 비어 있으면 통과
    """
    path = REPO_ROOT / relative
    if not path.exists():
        return [f"{relative}: 문서가 없습니다."]

    raw = path.read_text(encoding="utf-8")
    body = strip_code_fences(raw)
    # 헤딩도 펜스를 걷어낸 본문에서 찾는다. 셸 예제의 주석 줄(`# ...`)이 헤딩으로
    # 잡히면 실재하지 않는 앵커가 유효한 것처럼 통과해버린다.
    headings = {anchor_slug(m.group(2)) for m in HEADING_PATTERN.finditer(body)}
    problems: list[str] = []

    for label, target in LINK_PATTERN.findall(body):
        if target.startswith(("http://", "https://", "mailto:")):
            continue

        file_part, _, anchor_part = target.partition("#")

        if file_part:
            resolved = (path.parent / file_part).resolve()
            if not resolved.exists():
                problems.append(
                    f"{relative}: [{label}]({target}) 가 가리키는 파일이 없습니다."
                )
                continue

        if anchor_part and not file_part and anchor_part not in headings:
            problems.append(
                f"{relative}: [{label}](#{anchor_part}) 에 해당하는 헤딩이 없습니다."
            )

    return problems


def main() -> int:
    """대상 문서 전체를 검사한다.

    :returns: 프로세스 종료 코드(0 통과, 1 실패)
    """
    all_problems: list[str] = []
    print(f"문서 링크 검사 {len(TARGET_DOCS)}건")
    for relative in TARGET_DOCS:
        problems = check_document(relative)
        mark = "ok  " if not problems else "FAIL"
        print(f"  [{mark}] {relative}")
        all_problems.extend(problems)

    if all_problems:
        # 표준출력이 파이프·파일로 리다이렉트되면 블록 버퍼링되어 표준에러보다
        # 늦게 화면에 나타난다. 위에서 출력한 문서 목록이 실패 요약보다
        # 먼저 보이도록 첫 표준에러 출력 전에 명시적으로 비운다.
        sys.stdout.flush()
        print("", file=sys.stderr)
        print(f"[실패] 끊어진 참조 {len(all_problems)}건", file=sys.stderr)
        for problem in all_problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(f"\n[통과] 문서 {len(TARGET_DOCS)}종의 상대 링크와 앵커가 모두 유효합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
