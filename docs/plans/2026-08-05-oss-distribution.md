# dartcatcher 오픈소스 배포 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dartcatcher가 CI·기여 문서·버전 릴리스를 갖춘 "운영되는 오픈소스"로 보이게 하고, 그 CI가 저장소의 강점인 근거 대조를 실제로 검사하게 한다.

**Architecture:** 검사 도구 2개(`tools/`)를 먼저 만들어 로컬에서 통과시킨 뒤 GitHub Actions로 올린다. 근거 대조는 기대값을 스크립트에 적지 않고 evidence·data 원본에서 파생해 README 문자열과 맞춰보는 방식이라, 어느 한쪽만 바뀌어도 깨진다. 기여 문서와 README 입구 분기표는 CI가 초록불이 된 뒤에 얹고, 버전 태그는 마지막에 붙인다.

**Tech Stack:** Python 3.13 표준 라이브러리, GitHub Actions, ruff, shellcheck

설계 근거: [`docs/specs/2026-08-05-oss-distribution-design.md`](../specs/2026-08-05-oss-distribution-design.md)

## Global Constraints

- **표준 라이브러리만.** `tools/` 의 두 스크립트는 `pip install` 없이 돌아야 한다. 저장소에 `requirements.txt` 를 만들지 않는다.
- **네트워크 금지.** CI는 DART 서버에 요청을 보내지 않는다. 파이프라인을 CI에서 실행하지 않는다. README "크롤링 윤리" 절의 최소 페이지 원칙과 어긋나기 때문이다.
- **JSDoc 한국어 필수.** 모든 함수·클래스·상수에 한국어 docstring을 단다. `:param:` / `:returns:` / `:raises:` 를 포함한다. 기존 `api/fetch_disclosures.py` 의 스타일을 그대로 따른다.
- **커밋 메시지.** Conventional Commits + 한국어 본문. `<type>: <제목>` 형식.
- **main 직접 커밋 금지.** 모든 작업은 피처 브랜치와 PR을 거친다.
- **기존 코드 수정 금지.** `crawler/` `capture/` `ocr/` `api/` 의 파이썬 파일은 이번 계획에서 건드리지 않는다. ruff가 걸리면 코드가 아니라 `ruff.toml` 을 조정한다.
- **README 본문 유지.** README는 두 곳만 수정한다. 뱃지 줄과 "결과 한눈에" 위 입구 분기표. 기존 수치·문장·표는 그대로 둔다.
- **줄표 금지.** 문서에 em dash(`—`)와 en dash(`–`)를 쓰지 않는다. 커밋 `c66b0f6` 에서 37건을 제거해 0건을 만들어둔 상태다.

## 테스트 전략에 대한 참고

승인된 스펙이 단위 테스트를 범위 밖으로 두었다. 대신 검사 도구 자체가 테스트 하네스 역할을 한다. 각 도구는 다음 사이클로 검증한다.

1. 실제 데이터에 대고 실행 → 통과해야 한다 (green)
2. 입력을 일부러 어긋나게 만들고 실행 → 실패해야 한다 (red)
3. 되돌리고 재실행 → 다시 통과해야 한다 (green)

2번을 건너뛰면 "아무것도 검사하지 않는 초록불"이 되어 이 작업의 목적 자체가 무너진다. 반드시 수행한다.

## File Structure

| 파일 | 책임 |
| --- | --- |
| `tools/check_evidence.py` | evidence·data에서 수치를 파생해 README 문자열과 대조 |
| `tools/check_links.py` | README 5종의 상대 링크와 앵커 검증 |
| `ruff.toml` | lint 규칙 범위 고정 |
| `.github/workflows/ci.yml` | lint · docs · evidence 3잡 |
| `CONTRIBUTING.md` | 기여 절차와 근거 동반 원칙 |
| `SECURITY.md` | 인증키 취급, 취약점 신고 |
| `CODE_OF_CONDUCT.md` | Contributor Covenant 2.1 |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | 버그 신고 폼 |
| `.github/ISSUE_TEMPLATE/improvement.yml` | 개선 제안 폼 |
| `.github/ISSUE_TEMPLATE/config.yml` | 빈 이슈 비활성화 |
| `.github/pull_request_template.md` | 근거 첨부 체크리스트 |
| `CHANGELOG.md` | Keep a Changelog 형식 |
| `README.md` | 수정 2곳 |

## PR 분할

| PR | 브랜치 | 태스크 |
| --- | --- | --- |
| 기존 #4 | `docs/roadmap-api-done` | Task 0 |
| 1 | `ci/evidence-checks` | Task 1 ~ 4 |
| 2 | `docs/contributor-guides` | Task 5 ~ 7 |
| 3 | `chore/release-v0.1.0` | Task 8 ~ 9 |

PR 1을 머지해 CI 초록불을 확인한 뒤 PR 2를 연다. PR 2는 README를 수정하므로 새 CI가 자기 자신을 검사하게 된다.

---

### Task 0: PR #4 머지와 브랜치 정리

**Files:** 없음 (git 작업만)

**Interfaces:**
- Produces: `main` 이 `fe53e40` 을 포함한 상태. 이후 모든 브랜치가 여기서 갈라진다.

- [ ] **Step 1: PR #4 상태 확인**

```bash
gh pr view 4 --json number,title,state,mergeable
```

Expected: `"state": "OPEN"`, `"mergeable": "MERGEABLE"`

- [ ] **Step 2: PR #4 머지**

```bash
gh pr merge 4 --merge
```

- [ ] **Step 3: 로컬 main 갱신 확인**

```bash
git checkout main && git pull && git log --oneline -3
```

Expected: 최상단이 PR #4 머지 커밋. `fe53e40` 이 이력에 포함됨.

- [ ] **Step 4: 스펙 브랜치 푸시하고 PR 열기**

```bash
git push -u origin docs/oss-distribution-spec
gh pr create --title "docs: 오픈소스 배포 설계 스펙 추가" \
  --body "구현 전 설계 문서. 구현은 PR 3개로 나눠 진행한다."
```

---

### Task 1: 근거 대조 검사기

**Files:**
- Create: `tools/check_evidence.py`

**Interfaces:**
- Produces: `python3 tools/check_evidence.py` → exit 0(통과) 또는 1(실패). Task 4의 `evidence` 잡이 이 명령을 호출한다.

- [ ] **Step 1: 브랜치 생성**

```bash
git checkout main && git checkout -b ci/evidence-checks
```

- [ ] **Step 2: `tools/check_evidence.py` 작성**

```python
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
```

- [ ] **Step 3: 실제 데이터로 실행해 통과 확인 (green)**

Run: `python3 tools/check_evidence.py; echo "exit=$?"`

Expected:
```
근거 대조 8건
  [ok  ] OCR 한국어 정확도: 61.3%
  [ok  ] HiDPI 재측정 정확도: 83.9%
  [ok  ] 캡처 해상도(main): 1444×2469
  [ok  ] 캡처 크기(main): 410,541
  [ok  ] 캡처 해상도(search): 1444×1252
  [ok  ] 캡처 크기(search): 226,410
  [ok  ] 크롤 유니크 접수번호: 45건
  [ok  ] 산출물 개수: 5개씩
...
[통과] 8건 전부 README와 일치합니다.
exit=0
```

- [ ] **Step 4: README를 일부러 어긋나게 만들고 실패 확인 (red)**

```bash
python3 - <<'PY'
from pathlib import Path
p = Path("README.md")
p.write_text(p.read_text(encoding="utf-8").replace("61.3%", "62.3%"), encoding="utf-8")
PY
python3 tools/check_evidence.py; echo "exit=$?"
```

Expected: `[FAIL] OCR 한국어 정확도: 61.3%` 가 찍히고 `exit=1`

이 단계를 건너뛰면 안 된다. 검사기가 실제로 실패할 수 있는지 확인하지 않으면 아무것도 검사하지 않는 초록불과 구별되지 않는다.

- [ ] **Step 5: 되돌리고 재통과 확인 (green)**

```bash
git checkout README.md
python3 tools/check_evidence.py; echo "exit=$?"
```

Expected: `exit=0`

- [ ] **Step 6: 근거 파일 부재도 실패하는지 확인**

```bash
mv evidence/ocr_quality.txt /tmp/ocr_quality.txt.bak
python3 tools/check_evidence.py; echo "exit=$?"
mv /tmp/ocr_quality.txt.bak evidence/ocr_quality.txt
```

Expected: `[실패] 근거에서 수치를 파생하지 못했습니다: 근거 파일이 없습니다: evidence/ocr_quality.txt` 와 `exit=1`

- [ ] **Step 7: 커밋**

```bash
git add tools/check_evidence.py
git commit -m "$(cat <<'MSG'
feat: README 수치와 근거 파일을 대조하는 검사기 추가

README의 모든 주장에 근거 파일이 붙어 있다는 이 저장소의 강점은 문서와 근거가
같이 움직일 때만 유지된다. 한쪽만 고치면 조용히 깨지므로 검사기를 붙였다.

기대값을 스크립트에 적지 않는다. evidence·data 원본에서 수치를 계산해내고 그
문자열이 README에 있는지만 확인하므로, 검사기가 원본과 독립적으로 틀릴 여지가
없다. 어느 한쪽만 바뀌어도 깨진다. 대조 대상은 OCR 정확도 2건, 캡처 해상도·크기
4건, 크롤 접수번호, 산출물 개수로 모두 8건이다.

정확도는 적힌 백분율을 믿지 않고 분자·분모로 재계산해 대조한다. 근거 파일 자체가
앞뒤 안 맞는 경우를 잡기 위해서다. 근거 파일이 없거나 형식이 어긋나면 통과가
아니라 실패로 끝낸다. 검사가 조용히 0건이 되는 것이 이 장치의 유일한 실패
모드이고, evidence/compose_up_exitcode_trap.txt 에 기록해둔 함정과 같은 유형이다.

README를 62.3%로 고쳐 실패를, 되돌려 통과를, 근거 파일을 치워 실패를 각각
확인했다.
MSG
)"
```

---

### Task 2: 링크·앵커 검사기

**Files:**
- Create: `tools/check_links.py`

**Interfaces:**
- Consumes: 없음
- Produces: `python3 tools/check_links.py` → exit 0 또는 1. Task 4의 `docs` 잡이 호출한다.

- [ ] **Step 1: `tools/check_links.py` 작성**

```python
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
        print("", file=sys.stderr)
        print(f"[실패] 끊어진 참조 {len(all_problems)}건", file=sys.stderr)
        for problem in all_problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(f"\n[통과] 문서 {len(TARGET_DOCS)}종의 상대 링크와 앵커가 모두 유효합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 실행해 통과 확인 (green)**

Run: `python3 tools/check_links.py; echo "exit=$?"`

Expected: 5개 문서 전부 `[ok  ]`, `exit=0`

코드 펜스 제외가 동작하는지가 핵심이다. 루트 README 245~247행의 `(...)` 3건이 잡히면 펜스 처리가 안 된 것이다.

- [ ] **Step 3: 링크를 일부러 깨고 실패 확인 (red)**

```bash
python3 - <<'PY'
from pathlib import Path
p = Path("README.md")
p.write_text(p.read_text(encoding="utf-8").replace("(LICENSE)", "(LICENSE-NOPE)"), encoding="utf-8")
PY
python3 tools/check_links.py; echo "exit=$?"
```

Expected: `README.md: [MIT](LICENSE-NOPE) 가 가리키는 파일이 없습니다.` 와 `exit=1`

- [ ] **Step 4: 앵커도 깨지는지 확인 (red)**

```bash
git checkout README.md
python3 - <<'PY'
from pathlib import Path
p = Path("README.md")
p.write_text(p.read_text(encoding="utf-8").replace("## 로드맵", "## 향후 계획"), encoding="utf-8")
PY
python3 tools/check_links.py; echo "exit=$?"
```

Expected: `[로드맵](#로드맵) 에 해당하는 헤딩이 없습니다.` 와 `exit=1`

- [ ] **Step 5: 되돌리고 재통과 확인 (green)**

```bash
git checkout README.md
python3 tools/check_links.py; echo "exit=$?"
```

Expected: `exit=0`

- [ ] **Step 6: 커밋**

```bash
git add tools/check_links.py
git commit -m "$(cat <<'MSG'
feat: 문서 상대 링크·앵커 검사기 추가

이 저장소는 문서가 서로를 많이 참조한다. 루트 README가 모듈 README와 evidence
파일을 가리키고 목차가 본문 헤딩을 가리키는데, 파일을 옮기거나 헤딩 문구를 바꾸면
조용히 끊어진다. GitHub은 경고를 주지 않는다.

코드 펜스 안쪽은 건너뛴다. 루트 README의 크롤 결과 발췌에 (...) 로 줄여 적은
링크가 있어 그대로 검사하면 오탐 3건이 난다. 예시일 뿐 실제 링크가 아니다.
줄 번호를 유지하려고 펜스 내부를 삭제하지 않고 빈 줄로 치환한다.

LICENSE 링크를 깨서 실패를, 로드맵 헤딩 문구를 바꿔 앵커 실패를, 되돌려 통과를
각각 확인했다.
MSG
)"
```

---

### Task 3: lint 도구 로컬 검증과 설정

**Files:**
- Create: `ruff.toml` (필요한 경우에만)

**Interfaces:**
- Produces: `ruff check .` 와 `shellcheck run_pipeline.sh ocr/fetch_tessdata.sh` 가 통과하는 상태. Task 4의 `lint` 잡이 같은 명령을 쓴다.

이 태스크의 목적은 **CI를 만들기 전에 로컬에서 통과를 확인**하는 것이다. 첫 푸시부터 빨간불이면 "돌아가는 증거"라는 목적이 무너진다.

- [ ] **Step 1: 도구 설치**

```bash
python3 -m pip install --user ruff
brew install shellcheck
```

- [ ] **Step 2: ruff 기본 설정으로 실행**

Run: `ruff check .; echo "exit=$?"`

ruff 기본 select는 `E4,E7,E9,F` 로 좁아서 통과할 가능성이 높다. 통과하면 Step 3을 건너뛰고 Step 4로 간다.

- [ ] **Step 3: 걸리는 규칙이 있으면 `ruff.toml` 작성**

기존 코드를 고치지 않는다. 규칙 범위를 좁히는 쪽으로 해결한다.

```toml
# dartcatcher lint 설정
#
# 이 저장소는 표준 라이브러리만 쓰는 얇은 실행 스크립트 모음이다. 검사 범위를
# 문법 오류와 미사용 심볼 수준으로 좁게 잡는다. 스타일 통일은 이 프로젝트가
# 풀려는 문제가 아니며, 규칙을 넓히려고 동작하는 코드를 고치지 않는다.

target-version = "py313"
line-length = 100

exclude = [
    "data",
    "evidence",
    "ocr/tessdata",
]

[lint]
# E4 임포트, E7 문장, E9 문법 오류, F pyflakes
select = ["E4", "E7", "E9", "F"]
```

- [ ] **Step 4: ruff 재실행해 통과 확인**

Run: `ruff check .; echo "exit=$?"`

Expected: `All checks passed!` 와 `exit=0`

- [ ] **Step 5: shellcheck 실행**

Run: `shellcheck run_pipeline.sh ocr/fetch_tessdata.sh; echo "exit=$?"`

경고가 나오면 판단이 갈린다. `SC2086`(따옴표 없는 변수) 같은 실질적 지적이면 **셸 스크립트는 고친다.** 파이썬 코드를 안 고치는 것과 달리 셸은 검사 대상이 좁고 수정이 안전하다. 다만 수정 후 반드시 Step 6을 수행한다.

- [ ] **Step 6: 셸을 고쳤다면 파이프라인이 여전히 도는지 확인**

```bash
bash -n run_pipeline.sh && bash -n ocr/fetch_tessdata.sh && echo "문법 검사 통과"
bash run_pipeline.sh --skip-crawl
```

Expected: 캡처·OCR 단계가 정상 종료. 도커가 없는 환경이면 문법 검사만 하고 넘어가되, 그 사실을 커밋 메시지에 적는다.

- [ ] **Step 7: 커밋**

```bash
git add -A
git commit -m "$(cat <<'MSG'
chore: lint 도구 설정과 셸 스크립트 정리

CI를 올리기 전에 ruff와 shellcheck를 로컬에서 먼저 돌려 통과를 확인했다. 첫
푸시부터 빨간불이면 "돌아가는 증거"라는 목적이 무너지기 때문이다.

ruff는 검사 범위를 E4·E7·F9·F로 좁게 잡았다. 이 저장소는 표준 라이브러리만 쓰는
얇은 실행 스크립트 모음이고 스타일 통일은 이 프로젝트가 풀려는 문제가 아니다.
규칙을 넓히려고 동작하는 코드를 고치지 않는다. data·evidence·tessdata는 검사에서
제외했다.
MSG
)"
```

---

### Task 4: GitHub Actions 워크플로

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: Task 1의 `tools/check_evidence.py`, Task 2의 `tools/check_links.py`, Task 3의 `ruff.toml`
- Produces: `CI` 라는 이름의 워크플로. Task 7의 README 뱃지가 이 이름을 참조한다.

- [ ] **Step 1: `.github/workflows/ci.yml` 작성**

```yaml
# dartcatcher CI
#
# 파이프라인 자체는 CI에서 돌리지 않는다. 이미지 합계가 약 14GB인 것보다,
# 실행할 때마다 DART 서버에 요청을 보내게 되어 README "크롤링 윤리" 절의
# 최소 페이지 원칙과 어긋나는 것이 더 큰 이유다.
#
# 대신 네트워크 없이 확인할 수 있는 것을 검사한다. 특히 evidence 잡은 README의
# 수치가 근거 파일과 어긋나지 않는지 대조한다. 이 저장소의 강점이 "모든 주장에
# 근거가 붙어 있다"인 만큼, 뱃지가 그 강점 자체를 보증하게 만든 것이다.

name: CI

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  lint:
    name: lint (ruff, shellcheck)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: ruff 설치
        run: python -m pip install ruff

      - name: ruff
        run: ruff check .

      - name: shellcheck
        run: shellcheck run_pipeline.sh ocr/fetch_tessdata.sh

  docs:
    name: docs (링크, 앵커)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: 상대 링크와 앵커 검사
        run: python3 tools/check_links.py

  evidence:
    name: evidence (README 수치 대조)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: README 수치를 근거 파일과 대조
        run: python3 tools/check_evidence.py
```

`shellcheck` 는 ubuntu-latest 러너에 이미 설치돼 있어 별도 설치 단계가 없다.

- [ ] **Step 2: 워크플로 문법 확인**

```bash
python3 -c "
import sys
try:
    import yaml
except ImportError:
    sys.exit('PyYAML 없음. 이 단계는 건너뛰고 푸시 후 Actions 탭에서 확인한다.')
d = yaml.safe_load(open('.github/workflows/ci.yml'))
print('잡:', list(d['jobs'].keys()))
assert set(d['jobs']) == {'lint','docs','evidence'}
print('문법 확인 통과')
"
```

- [ ] **Step 3: 커밋하고 푸시**

```bash
git add .github/workflows/ci.yml
git commit -m "$(cat <<'MSG'
ci: lint·docs·evidence 3잡 워크플로 추가

파이프라인은 CI에서 돌리지 않는다. 이미지 합계 14GB보다도, 실행할 때마다 DART
서버에 요청을 보내게 되어 README "크롤링 윤리" 절의 최소 페이지 원칙과 어긋나는
것이 더 큰 이유다.

대신 네트워크 없이 확인 가능한 것을 검사한다. lint는 ruff와 shellcheck, docs는
문서 상대 링크와 앵커, evidence는 README 수치와 근거 파일의 대조다. 세 잡은 서로
의존하지 않아 병렬로 돈다.

evidence 잡이 이 워크플로의 핵심이다. 이 저장소의 강점이 "모든 주장에 근거 파일이
붙어 있다"인 만큼, 아무것도 검사하지 않는 초록 뱃지를 다는 것은 그 정체성과
모순된다. 뱃지가 강점 자체를 보증하게 만들었다.
MSG
)"
git push -u origin ci/evidence-checks
```

- [ ] **Step 4: PR 열고 CI 초록불 확인**

```bash
gh pr create --title "ci: 근거 대조 CI 추가" --body "$(cat <<'BODY'
README 수치가 evidence 파일과 어긋나면 빨간불이 되는 CI를 붙였다.

## 잡
- `lint`: ruff, shellcheck
- `docs`: 문서 상대 링크와 앵커
- `evidence`: README 수치 8건을 근거 파일에서 파생해 대조

## 검증
- 로컬에서 세 검사 전부 통과 확인
- README를 62.3%로 고쳐 evidence 실패 확인, 되돌려 통과 확인
- LICENSE 링크를 깨서 docs 실패 확인, 되돌려 통과 확인
- 근거 파일을 치워 파생 실패 확인

설계: `docs/specs/2026-08-05-oss-distribution-design.md`
BODY
)"
gh pr checks --watch
```

Expected: 3잡 전부 pass

- [ ] **Step 5: 머지**

```bash
gh pr merge --merge
git checkout main && git pull
```

---

### Task 5: 기여자 문서 3종

**Files:**
- Create: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`

**Interfaces:**
- Consumes: Task 1·2의 검사 명령 (CONTRIBUTING이 이를 안내한다)
- Produces: 없음

- [ ] **Step 1: 브랜치 생성**

```bash
git checkout main && git checkout -b docs/contributor-guides
```

- [ ] **Step 2: `CONTRIBUTING.md` 작성**

```markdown
# 기여 안내

이 저장소는 기성 도커 이미지를 조합해 DART 공시를 수집한 기록이다. 코드보다
**무엇이 막혔고 어떻게 우회했는지의 기록**이 본체에 가깝다. 기여도 그 성격을
따른다.

## 이 프로젝트의 한 가지 원칙

**수치를 바꾸면 근거도 같이 낸다.**

README의 모든 수치에는 `evidence/` 나 `data/` 에 근거 파일이 붙어 있다. 문서의
숫자를 고치는 변경은 그 숫자가 나온 실행 출력을 함께 제출해야 한다. 반대로 근거
파일을 갱신하면 README의 해당 수치도 같이 고쳐야 한다.

이건 예의가 아니라 **CI가 강제하는 규칙**이다. 한쪽만 바뀌면 `evidence` 잡이
빨간불이 된다.

```bash
python3 tools/check_evidence.py
```

측정하지 않은 것은 "미검증"이라고 적는다. 이 저장소는 OCR 정확도 61.3%라는 낮은
숫자를 첫 화면에 그대로 두고 있다. 숨기지 않는 것이 나머지 수치의 신뢰도를
만든다.

## 푸시 전에 돌릴 것

CI가 검사하는 것과 같은 명령이다. `pip install` 없이 돈다.

```bash
python3 tools/check_evidence.py   # README 수치와 근거 대조
python3 tools/check_links.py      # 문서 링크와 앵커
ruff check .                      # 파이썬 lint (ruff 필요)
shellcheck run_pipeline.sh ocr/fetch_tessdata.sh
```

파이프라인 자체를 바꿨다면 실제로 돌려보고 출력을 `evidence/` 에 남긴다.

```bash
bash run_pipeline.sh --stop-crawler
```

## 브랜치와 커밋

- `main` 에 직접 커밋하지 않는다. `<type>/<short>` 브랜치와 PR을 쓴다
- 커밋 메시지는 Conventional Commits 형식이다: `feat:` `fix:` `docs:` `ci:`
  `chore:` `refactor:`
- 본문에 **무엇을 왜** 바꿨는지 적는다. 이 저장소의 기존 커밋 메시지가 참고가
  된다

## 크롤링 대상을 늘리는 변경

수집 대상 URL을 추가하는 PR은 다음을 함께 제출한다.

1. 해당 사이트 `robots.txt` 원문과 그것을 근거로 한 판단
2. 요청 간격 설정값과 그렇게 정한 이유
3. 로그인·인증이 필요한 영역을 건드리지 않았다는 확인

README "크롤링 윤리" 절이 기준이다. 상대 서버는 남의 인프라다.

## 인증키

DART 인증키는 환경변수 `API_K_DART` 로만 넘긴다. `.env` 에도 쓰지 않는다.
자세한 것은 [SECURITY.md](SECURITY.md) 를 본다.

## 무엇에 기여하면 좋은가

README [로드맵](README.md#로드맵) 에 남은 항목이 출발점이다. 특히 다음이 측정
가능한 개선이다.

- 캡처 `device_scale_factor` 상향의 균형점 찾기 (실험에서 22.6%p 개선을 확인했으나
  1회 측정이라 미검증)
- OCR 전처리(이진화, 기울기 보정) 효과 측정
- `robots.txt` 자동 확인
- 대상 URL을 코드 상수에서 설정 파일로 분리
```

- [ ] **Step 3: `SECURITY.md` 작성**

```markdown
# 보안 정책

## 인증키 취급

이 저장소는 두 종류의 비밀값을 쓴다. 둘 다 저장소에 커밋하지 않는다.

| 값 | 용도 | 보관 |
| --- | --- | --- |
| `CRAWL4AI_API_TOKEN` | crawl4ai 컨테이너 인증 | `.env` (`.gitignore` 대상). `run_pipeline.sh` 가 없으면 만든다 |
| `API_K_DART` | DART 공식 OpenAPI 인증키 | 셸 환경변수로만. `.env` 에도 쓰지 않는다 |

`API_K_DART` 를 `.env` 에 두지 않는 이유는, 이 저장소의 `.env` 가 crawl4ai 토큰
전용이고 키 파일이 하나 늘면 실수로 커밋할 표면도 늘기 때문이다.

`api/` 의 두 스크립트는 인증키를 로그에 찍지 않는다. 요청 주소를 출력할 때
`crtfc_key` 자리를 `***` 로 바꾸고, HTTP 오류가 나도 마스킹한 주소만 남긴다.
산출물 JSON에 저장하는 `request_url` 도 마스킹된 형태다.

기여할 때 키를 다루는 코드를 건드린다면 이 성질이 유지되는지 확인한다.

## 취약점 신고

키가 로그나 산출물에 새는 경로를 발견했거나 다른 보안 문제를 찾았다면, 공개
이슈로 열지 말고 저장소 소유자에게 GitHub의
[Private vulnerability reporting](https://github.com/Noah-TaeHwan/dartcatcher/security/advisories/new)
으로 알려주기 바란다.

## 지원 범위

이 저장소는 동작 검증용 예제이며 운영 환경을 위한 것이 아니다. 버전 지원 정책은
두지 않는다. 최신 `main` 을 기준으로 대응한다.
```

- [ ] **Step 4: `CODE_OF_CONDUCT.md` 작성**

Contributor Covenant 2.1 **영문** 원문을 쓴다. 저장소의 다른 문서는 한국어지만
행동강령은 국제 표준 문안이라 원문 그대로 두는 것이 통용된다. 번역본을 직접 만들면
문안의 법적·규범적 정확성을 담보할 수 없다.

```bash
curl -fsSL https://www.contributor-covenant.org/version/2/1/code_of_conduct/code_of_conduct.md \
  -o CODE_OF_CONDUCT.md
```

내려받은 뒤 연락처 자리를 채운다. Contributor Covenant 2.1의 플레이스홀더 문구는
`[INSERT CONTACT METHOD]` 이지만 배포본에 따라 다를 수 있어, 치환 대상을 못 찾으면
멈추고 사람이 파일을 확인하게 한다.

```bash
python3 - <<'PY'
import sys
from pathlib import Path

p = Path("CODE_OF_CONDUCT.md")
if not p.exists() or p.stat().st_size == 0:
    sys.exit("내려받기에 실패했습니다. 네트워크를 확인하거나 파일을 직접 만드세요.")

text = p.read_text(encoding="utf-8")
if "[INSERT CONTACT METHOD]" not in text:
    sys.exit(
        "치환 대상 '[INSERT CONTACT METHOD]' 를 찾지 못했습니다. "
        "파일을 열어 연락처 자리를 직접 채우세요."
    )

p.write_text(
    text.replace("[INSERT CONTACT METHOD]", "noah.taehwan@gmail.com"),
    encoding="utf-8",
)
print("연락처 치환 완료")
PY
```

- [ ] **Step 5: 검사 통과 확인**

```bash
python3 tools/check_links.py; echo "exit=$?"
python3 tools/check_evidence.py; echo "exit=$?"
```

Expected: 둘 다 `exit=0`

`CONTRIBUTING.md` 가 `README.md#로드맵` 앵커와 `SECURITY.md` 를 가리키지만, `check_links.py` 의 `TARGET_DOCS` 에는 아직 없어 검사되지 않는다. Task 7에서 추가한다.

- [ ] **Step 6: 커밋**

```bash
git add CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md
git commit -m "$(cat <<'MSG'
docs: 기여 안내·보안 정책·행동강령 추가

CONTRIBUTING은 이 프로젝트의 성격에 맞춰 한 가지 원칙을 앞세웠다. 수치를 바꾸면
근거도 같이 낸다는 것이다. 예의 차원이 아니라 CI의 evidence 잡이 강제하는 규칙이며,
한쪽만 바뀌면 빨간불이 된다. 푸시 전에 돌릴 명령 네 개와, 크롤링 대상을 늘리는
PR이 함께 제출해야 할 세 가지(robots.txt 판단, 요청 간격 근거, 인증 영역 미접근
확인)도 적었다.

SECURITY는 이 저장소가 쓰는 비밀값 두 종류의 보관 위치를 나눠 적었다. API_K_DART를
.env에 두지 않는 이유(키 파일이 늘면 실수로 커밋할 표면도 는다)와, api/ 스크립트가
로그·산출물에서 키를 마스킹하는 성질을 유지해달라는 요청을 포함했다.

행동강령은 Contributor Covenant 2.1이다.
MSG
)"
```

---

### Task 6: 이슈·PR 템플릿

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`, `.github/ISSUE_TEMPLATE/improvement.yml`, `.github/ISSUE_TEMPLATE/config.yml`, `.github/pull_request_template.md`

**Interfaces:**
- Consumes: Task 5의 `CONTRIBUTING.md` (템플릿이 이를 참조)

- [ ] **Step 1: `.github/ISSUE_TEMPLATE/bug_report.yml` 작성**

```yaml
name: 버그 신고
description: 파이프라인이 문서대로 동작하지 않는 경우
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        이 저장소는 실행 환경에 따라 결과가 달라지는 부분이 많습니다.
        환경 정보를 함께 적어주시면 재현이 빨라집니다.

  - type: dropdown
    id: stage
    attributes:
      label: 어느 단계인가요
      options:
        - "1. 크롤 (crawl4ai)"
        - "2. 캡처 (Playwright)"
        - "3. OCR (tesseract)"
        - "api/ 공식 OpenAPI 조회"
        - "run_pipeline.sh 또는 docker compose"
        - "문서"
    validations:
      required: true

  - type: textarea
    id: what-happened
    attributes:
      label: 무엇이 일어났나요
      description: 실행한 명령과 그 출력을 그대로 붙여주세요. 인증키는 지워주세요.
      render: shell
    validations:
      required: true

  - type: textarea
    id: expected
    attributes:
      label: 무엇을 기대했나요
    validations:
      required: true

  - type: textarea
    id: environment
    attributes:
      label: 환경
      description: "`docker version` 과 `python3 --version` 출력, OS와 아키텍처"
      placeholder: |
        Docker 29.6.2
        Python 3.13.1
        macOS 15.6 arm64
      render: shell
    validations:
      required: true
```

- [ ] **Step 2: `.github/ISSUE_TEMPLATE/improvement.yml` 작성**

```yaml
name: 개선 제안
description: 정확도, 문서, 구조에 대한 제안
labels: ["enhancement"]
body:
  - type: markdown
    attributes:
      value: |
        README 로드맵에 남은 항목이라면 그것을 언급해주세요.
        측정 가능한 제안일수록 반영이 빠릅니다.

  - type: textarea
    id: proposal
    attributes:
      label: 무엇을 바꾸자는 제안인가요
    validations:
      required: true

  - type: textarea
    id: rationale
    attributes:
      label: 왜 그렇게 보시나요
      description: |
        측정값이 있다면 함께 적어주세요. 이 저장소는 근거 없는 수치를 문서에
        넣지 않습니다. 아직 측정하지 않았다면 "미검증"이라고 적어주셔도 됩니다.
    validations:
      required: true

  - type: checkboxes
    id: scope
    attributes:
      label: 확인
      options:
        - label: README 로드맵에 이미 있는 항목인지 확인했습니다
        - label: 기존 이슈에 같은 제안이 없는지 확인했습니다
```

- [ ] **Step 3: `.github/ISSUE_TEMPLATE/config.yml` 작성**

```yaml
blank_issues_enabled: false
contact_links:
  - name: 보안 문제 신고
    url: https://github.com/Noah-TaeHwan/dartcatcher/security/advisories/new
    about: 인증키 유출 경로 등 보안 문제는 공개 이슈가 아닌 이쪽으로 알려주세요.
  - name: 기여 안내
    url: https://github.com/Noah-TaeHwan/dartcatcher/blob/main/CONTRIBUTING.md
    about: PR을 보내기 전에 읽어주세요.
```

- [ ] **Step 4: `.github/pull_request_template.md` 작성**

```markdown
## 무엇을 바꿨나

<!-- 한두 문장으로. 왜 필요한 변경인지 포함해주세요. -->

## 어떻게 확인했나

<!--
실행한 명령과 그 출력을 붙여주세요. "동작합니다"만으로는 부족합니다.
이 저장소는 주장에 근거를 붙이는 것을 원칙으로 합니다.
-->

```
(실행 출력)
```

## 체크리스트

- [ ] `python3 tools/check_evidence.py` 통과
- [ ] `python3 tools/check_links.py` 통과
- [ ] `ruff check .` 통과
- [ ] 문서의 수치를 바꿨다면, 그 수치가 나온 실행 출력을 `evidence/` 에 함께 넣었다
- [ ] 크롤링 대상을 늘렸다면, `robots.txt` 판단 근거와 요청 간격을 적었다
- [ ] 인증키나 토큰이 diff에 들어가지 않았다
```

- [ ] **Step 5: YAML 문법 확인**

```bash
python3 - <<'PY'
import sys
from pathlib import Path
try:
    import yaml
except ImportError:
    sys.exit("PyYAML 없음. 푸시 후 GitHub 이슈 탭에서 템플릿이 뜨는지 확인한다.")
for p in sorted(Path(".github/ISSUE_TEMPLATE").glob("*.yml")):
    yaml.safe_load(p.read_text(encoding="utf-8"))
    print(f"ok {p}")
PY
```

- [ ] **Step 6: 커밋**

```bash
git add .github/ISSUE_TEMPLATE .github/pull_request_template.md
git commit -m "$(cat <<'MSG'
docs: 이슈·PR 템플릿 추가

버그 신고 폼은 어느 단계인지부터 고르게 했다. 이 저장소는 세 단계가 서로 다른
컨테이너를 쓰고 실행 환경에 따라 결과가 달라지는 부분이 많아서, 단계와 환경
정보가 있어야 재현이 된다.

개선 제안 폼은 측정값을 함께 적도록 안내하되 "미검증"으로 적어도 되게 열어뒀다.
근거 없는 수치를 문서에 넣지 않는다는 원칙을 제안 단계부터 공유하기 위해서다.

PR 템플릿의 체크리스트에 검사 명령 세 개와, 수치를 바꿨을 때 근거를 함께 넣었는지,
크롤링 대상을 늘렸을 때 robots.txt 판단을 적었는지를 넣었다. 빈 이슈는 비활성화하고
보안 문제는 공개 이슈 대신 private reporting으로 보낸다.
MSG
)"
```

---

### Task 7: README 입구 분기표와 CI 뱃지

**Files:**
- Modify: `README.md` (뱃지 줄, "결과 한눈에" 위)
- Modify: `tools/check_links.py` (`TARGET_DOCS` 에 새 문서 추가)

**Interfaces:**
- Consumes: Task 4의 워크플로 이름 `CI`, Task 5의 `CONTRIBUTING.md`·`SECURITY.md`

- [ ] **Step 1: CI 뱃지 추가**

`README.md` 9행 `[![License]...` 줄 **위에** 다음 줄을 넣는다. CI 뱃지가 맨 앞에 오는 것이 맞다. 정적 이미지가 아니라 실제 상태이기 때문이다.

```markdown
[![CI](https://github.com/Noah-TaeHwan/dartcatcher/actions/workflows/ci.yml/badge.svg)](https://github.com/Noah-TaeHwan/dartcatcher/actions/workflows/ci.yml)
```

- [ ] **Step 2: 입구 분기표 삽입**

`README.md` 의 `## 결과 한눈에` **바로 위에** 다음을 넣는다.

```markdown
## 당신이 여기 왔다면

| 찾는 것 | 갈 곳 |
| --- | --- |
| 기성 도커 이미지를 조합해 수집 계층을 만드는 방법 | 이 문서를 계속 읽는다 |
| DART 공시 데이터가 필요하다 | [`api/`](api/README.md) 공식 OpenAPI가 먼저다. 크롤링은 그다음이다 |
| 컨테이너에서 한국어 OCR을 돌려야 한다 | [`ocr/`](ocr/README.md) tessdata 주입 경로 |
| Docker Compose 원샷 잡 사슬이 조용히 성공으로 끝난다 | [`evidence/compose_up_exitcode_trap.txt`](evidence/compose_up_exitcode_trap.txt) |
| 이 프로젝트에 기여하고 싶다 | [CONTRIBUTING.md](CONTRIBUTING.md) |

```

- [ ] **Step 3: 목차에 새 절 추가**

`## 목차` 의 첫 항목 `- [개요](#개요)` **위에** 넣는다.

```markdown
- [당신이 여기 왔다면](#당신이-여기-왔다면)
```

- [ ] **Step 4: `check_links.py` 의 검사 대상 확장**

`TARGET_DOCS` 리스트를 다음으로 바꾼다.

```python
TARGET_DOCS = [
    "README.md",
    "crawler/README.md",
    "capture/README.md",
    "ocr/README.md",
    "api/README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
]
```

- [ ] **Step 5: 검사 통과 확인**

```bash
python3 tools/check_links.py; echo "exit=$?"
python3 tools/check_evidence.py; echo "exit=$?"
```

Expected: 둘 다 `exit=0`. `check_links` 가 문서 7종을 검사한다고 출력한다.

새 앵커 `#당신이-여기-왔다면` 이 목차에서 걸리지 않아야 한다. 걸리면 `anchor_slug` 가 한글을 제대로 처리하지 못한 것이므로 Task 2로 돌아간다.

- [ ] **Step 6: 커밋하고 PR**

```bash
git add README.md tools/check_links.py
git commit -m "$(cat <<'MSG'
docs: README 입구 분기표와 CI 뱃지 추가

README가 이 저장소를 "수집 파이프라인"으로 소개하는데, 정작 api/README.md 는
"259건이 오는 것을 3페이지 긁어 45건 얻는 것과 비교할 이유가 없다"고 적혀 있어
저장소가 자기 본체를 반박하는 구조였다. 첫 화면에서 방문자를 네 갈래로 나눠
보내는 표를 넣어 이 어긋남을 해소했다.

DART 데이터가 필요해서 온 사람은 api/ 로, 컨테이너에서 한국어 OCR을 하려는
사람은 ocr/ 로, Compose 종료코드 함정을 겪은 사람은 evidence/ 로 바로 간다.
도커 조합 자체가 궁금한 사람만 본문을 계속 읽는다. 세 모듈 문서는 원래도 그
내용을 담고 있었지만 입구가 없어 닿지 못했다.

CI 뱃지는 기존 정적 뱃지 여섯 개보다 앞에 뒀다. 유일하게 실제 상태를 반영하는
뱃지이기 때문이다.

check_links.py 의 검사 대상에 CONTRIBUTING.md 와 SECURITY.md 를 추가했다.
MSG
)"
git push -u origin docs/contributor-guides
gh pr create --title "docs: 기여자 문서와 README 입구 분기표" --body "$(cat <<'BODY'
CI가 초록불인 것을 확인한 뒤 기여 문서를 얹는다. 이 PR은 README를 수정하므로
직전 PR에서 만든 evidence·docs 잡이 자기 자신을 검사하게 된다.

## 추가
- `CONTRIBUTING.md`: "수치를 바꾸면 근거도 같이 낸다" 원칙, 푸시 전 검사 명령
- `SECURITY.md`: 비밀값 두 종류의 보관 위치, 키 마스킹 성질
- `CODE_OF_CONDUCT.md`: Contributor Covenant 2.1
- 이슈 템플릿 2종 + PR 템플릿

## 수정
- README: 입구 분기표, CI 뱃지, 목차 항목
- `check_links.py`: 검사 대상에 새 문서 2종 추가

설계: `docs/specs/2026-08-05-oss-distribution-design.md`
BODY
)"
gh pr checks --watch
```

Expected: 3잡 전부 pass

- [ ] **Step 7: 머지**

```bash
gh pr merge --merge
git checkout main && git pull
```

---

### Task 8: CHANGELOG

**Files:**
- Create: `CHANGELOG.md`

**Interfaces:**
- Produces: `v0.1.0` 절. Task 9의 GitHub Release 본문이 여기서 나온다.

- [ ] **Step 1: 브랜치 생성**

```bash
git checkout main && git checkout -b chore/release-v0.1.0
```

- [ ] **Step 2: `CHANGELOG.md` 작성**

```markdown
# 변경 이력

이 문서는 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따르고
버전은 [유의적 버전](https://semver.org/lang/ko/)을 따른다.

## [Unreleased]

## [0.1.0] - 2026-08-05

첫 공개 버전. 크롤·캡처·OCR 3단계 파이프라인과 공식 OpenAPI 교차 검증이 모두
실측으로 검증된 상태다.

### 추가

- 크롤·캡처·OCR 3단계 도커 파이프라인. 호스트에 런타임을 설치하지 않고 기성
  이미지 세 종을 조합한다
- `run_pipeline.sh`: 3단계 순차 실행. 토큰 생성과 학습 데이터 내려받기를 포함한다
- `docker-compose.yml`: 같은 파이프라인의 선언적 정의. `depends_on` 사슬로
  crawl4ai(healthy) → crawl → capture → ocr 순서를 강제한다
- `api/fetch_disclosures.py`: DART 공식 OpenAPI로 공시 목록 조회. `total_page`
  만큼 순회해 하루치를 전부 받는다
- `api/cross_check.py`: 크롤 결과와 공식 API 응답 대조
- `ocr/eval_quality.py`: 손으로 옮긴 정답지 62건과 대조한 정확도 측정
- `tools/check_evidence.py`: README 수치를 근거 파일에서 파생해 대조하는 검사기
- `tools/check_links.py`: 문서 상대 링크와 앵커 검사기
- CI 워크플로 3잡: lint, docs, evidence
- 기여 안내, 보안 정책, 행동강령, 이슈·PR 템플릿

### 실측 결과 (2026-08-05 KST, macOS arm64, Docker 29.6.2)

- 크롤: 공시 목록 3페이지에서 접수번호 기준 45건, 페이지 간 중복 0, 전부 HTTP 200
- 캡처: 전체 페이지 PNG 1444×2469 / 1444×1252, 폰트 추가 설치 없이 한글 렌더링
- OCR: 한국어 정확 일치 61.3%(38/62), 영어 인용문 10/10, 저자명 8/8
- 교차 검증: 크롤 45건이 공식 API에서 100% 확인. 반대로 크롤 구간 안에서 화면
  목록이 빠뜨린 공시 3건 발견
- 실행 시간: 3단계 순차 1분 58초 ~ 5분 2초 (이미지를 이미 받아둔 상태)

### 알려진 한계

- OCR 한국어 정확도 61.3%는 하류 분석에 그대로 넣을 수 없는 수준이다. 사람이
  확인하는 보조 자료로만 쓴다
- 캡처 해상도를 2배로 올리면 83.9%까지 오르나 1페이지 1회 측정이라 **미검증**이다
- 수집 대상 URL이 코드에 상수로 박혀 있다
- `robots.txt` 를 코드로 파싱해 자동으로 지키지 않는다. 사람이 한 번 읽고 판단한
  결과를 코드에 반영한 방식이다
- crawl4ai 이미지만 버전 태그가 없어 `latest` 를 쓴다. 검증 시점 버전은 0.9.2였다
- 재실행 시 산출물이 계속 쌓인다. 정리 정책이 없다

[Unreleased]: https://github.com/Noah-TaeHwan/dartcatcher/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Noah-TaeHwan/dartcatcher/releases/tag/v0.1.0
```

- [ ] **Step 3: 검사 통과 확인**

```bash
python3 tools/check_evidence.py; echo "exit=$?"
python3 tools/check_links.py; echo "exit=$?"
```

Expected: 둘 다 `exit=0`

CHANGELOG에 적은 수치(61.3%, 45건, 1444×2469)는 README와 같은 값이다. 다르면 근거 대조가 README만 보므로 잡히지 않는다. 사람이 한 번 눈으로 대조한다.

- [ ] **Step 4: 커밋**

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'MSG'
docs: CHANGELOG 추가, v0.1.0 정리

Keep a Changelog 형식으로 첫 공개 버전까지의 변경을 정리했다.

추가 항목만 나열하지 않고 실측 결과와 알려진 한계를 같은 비중으로 적었다.
OCR 정확도 61.3%가 하류 분석에 쓸 수 없는 수준이라는 것, 해상도 실험의 83.9%가
1회 측정이라 미검증이라는 것, robots.txt를 자동으로 지키지 않는다는 것을 릴리스
노트 단계에서 먼저 밝힌다. 릴리스 노트가 홍보문이 되면 README의 정직함과
어긋난다.
MSG
)"
```

---

### Task 9: v0.1.0 태그와 GitHub Release

**Files:** 없음 (git 태그와 GitHub Release)

**Interfaces:**
- Consumes: Task 8의 `CHANGELOG.md`

- [ ] **Step 1: PR 열고 머지**

```bash
git push -u origin chore/release-v0.1.0
gh pr create --title "docs: CHANGELOG 추가, v0.1.0 준비" --body "$(cat <<'BODY'
첫 공개 버전까지의 변경을 Keep a Changelog 형식으로 정리했다.
머지 후 v0.1.0 태그를 붙인다.

설계: `docs/specs/2026-08-05-oss-distribution-design.md`
BODY
)"
gh pr checks --watch
gh pr merge --merge
git checkout main && git pull
```

- [ ] **Step 2: 태그를 붙이기 전 마지막 확인**

```bash
python3 tools/check_evidence.py && python3 tools/check_links.py && echo "검사 통과"
git log --oneline -1
gh run list --branch main --limit 1
```

Expected: 검사 통과, main의 최신 CI가 성공 상태

- [ ] **Step 3: 태그 생성과 푸시**

```bash
git tag -a v0.1.0 -m "v0.1.0: 크롤·캡처·OCR 파이프라인과 공식 API 교차 검증"
git push origin v0.1.0
```

- [ ] **Step 4: GitHub Release 생성**

```bash
gh release create v0.1.0 \
  --title "v0.1.0" \
  --notes "$(cat <<'BODY'
크롤·캡처·OCR 3단계 도커 파이프라인과 공식 OpenAPI 교차 검증의 첫 공개 버전이다.
호스트에는 아무 런타임도 설치하지 않고 기성 이미지 세 종을 조합했다.

## 실측 결과 (2026-08-05 KST, macOS arm64, Docker 29.6.2)

| 단계 | 결과 |
| --- | --- |
| 크롤 | 공시 45건, 페이지 간 중복 0, 전부 HTTP 200 |
| 캡처 | 전체 페이지 PNG 1444×2469 / 1444×1252, 폰트 추가 설치 없이 한글 렌더링 |
| OCR | 한국어 정확 일치 61.3%(38/62), 영어 10/10 |
| 교차 검증 | 크롤 45건이 공식 API에서 100% 확인. 화면 목록이 빠뜨린 공시 3건 발견 |

출력 원문은 전부 `evidence/` 에 있다.

## 알려진 한계

OCR 한국어 정확도 61.3%는 하류 분석에 그대로 넣을 수 없다. 사람이 확인하는 보조
자료 수준이다. 캡처 해상도를 2배로 올리면 83.9%까지 오르지만 1페이지 1회 측정이라
**미검증**이다. 수집 대상 URL은 코드 상수로 박혀 있고 `robots.txt` 를 자동으로
지키지 않는다.

전체 목록은 [CHANGELOG.md](https://github.com/Noah-TaeHwan/dartcatcher/blob/main/CHANGELOG.md) 를 본다.

## 대량 수집이 목적이라면

이 파이프라인이 아니라 [DART OPEN API](https://opendart.fss.or.kr) 를 쓴다.
`api/` 모듈이 그 경로를 구현해두었다. 이 파이프라인은 API가 닿지 않는 표면을
메우는 보완 수단이다.
BODY
)"
```

- [ ] **Step 5: 결과 확인**

```bash
gh release view v0.1.0
gh repo view --json stargazerCount,description
```

Expected: Release 페이지가 뜨고 태그가 `v0.1.0` 으로 연결됨

- [ ] **Step 6: 저장소 설명과 토픽 갱신**

포지셔닝 변경을 GitHub description에도 반영한다.

```bash
gh repo edit --description "Three-stage Docker pipeline (crawl, capture, OCR) for Korean DART filings, assembled from off-the-shelf images. Every README number is backed by a checked-in run log and verified in CI."
gh repo edit --add-topic docker-compose --add-topic korean --add-topic tesseract-ocr
```

---

## 완료 기준

전부 만족해야 완료다.

- [ ] `main` 의 CI가 초록불이고, 3잡이 실제로 검사를 수행한다
- [ ] `python3 tools/check_evidence.py` 가 8건을 대조하고 통과한다
- [ ] README 수치를 하나 고치면 CI가 빨간불이 되는 것을 실제로 확인했다
- [ ] `v0.1.0` 태그와 GitHub Release가 존재한다
- [ ] README 첫 화면에서 네 부류의 방문자가 각자 갈 곳을 찾을 수 있다
- [ ] 열린 PR이 없고 작업 브랜치가 정리됐다
- [ ] `git log --first-parent main` 에 직접 커밋이 없다
