#!/usr/bin/env python3
"""캡처된 PNG에서 텍스트를 뽑아내는 OCR 실행 스크립트.

``data/captures/`` 의 PNG를 하나씩 ``jitesoft/tesseract-ocr`` 컨테이너에 넣어
한국어+영어(``-l kor+eng``) OCR을 돌리고, 결과 텍스트를 ``data/ocr/`` 에 저장한다.
호스트에는 tesseract를 설치하지 않으며 컨테이너만 사용한다.

이미지에 들어 있는 언어 데이터는 eng/equ/osd 뿐이라 한국어 인식이 불가능하다.
그래서 ``ocr/tessdata/`` 를 컨테이너에 마운트하고 ``TESSDATA_PREFIX`` 를 그쪽으로
돌려 kor 모델을 쓰게 한다. 학습 데이터는 ``ocr/fetch_tessdata.sh`` 로 받는다.

표준 라이브러리만 사용한다.

실행 예::

    python3 ocr/run_ocr.py                 # data/captures/*.png 전부
    python3 ocr/run_ocr.py --lang kor      # 언어 바꿔서
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CAPTURE_DIR = REPO_ROOT / "data" / "captures"
OUTPUT_DIR = REPO_ROOT / "data" / "ocr"
TESSDATA_DIR = REPO_ROOT / "ocr" / "tessdata"

# 태그 고정: latest 가 조용히 올라가 결과가 달라지는 것을 막는다.
OCR_IMAGE = "jitesoft/tesseract-ocr:5.5.2"

# 컨테이너 안에서 저장소 루트가 마운트되는 위치.
WORKDIR_IN_CONTAINER = "/work"

# 한 장당 OCR 제한 시간(초). 전체 페이지 캡처는 세로로 길어 시간이 꽤 걸린다.
OCR_TIMEOUT_SEC = 300

# 품질 지표 계산용 정규식.
HANGUL_RE = re.compile(r"[가-힣]")
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")


@dataclass
class OcrResult:
    """PNG 한 장에 대한 OCR 결과 요약.

    Attributes:
        image: 입력 PNG의 저장소 상대 경로.
        text_file: 저장된 텍스트 파일의 저장소 상대 경로(실패 시 None).
        ok: OCR 성공 여부.
        lang: 사용한 tesseract 언어 조합.
        chars: 추출된 전체 문자 수(공백 포함).
        non_empty_lines: 공백만 있는 줄을 제외한 줄 수.
        hangul_chars: 완성형 한글 음절 수.
        ascii_letter_chars: 영문 알파벳 수.
        elapsed_sec: OCR에 걸린 시간(초).
        error: 실패 사유(성공 시 None).
    """

    image: str
    text_file: str | None
    ok: bool
    lang: str
    chars: int = 0
    non_empty_lines: int = 0
    hangul_chars: int = 0
    ascii_letter_chars: int = 0
    elapsed_sec: float = 0.0
    error: str | None = None


def ensure_prerequisites() -> None:
    """docker 실행 파일과 한국어 학습 데이터가 준비됐는지 확인한다.

    Raises:
        SystemExit: docker가 없거나 kor.traineddata가 없는 경우.
    """
    if shutil.which("docker") is None:
        sys.exit("docker 명령을 찾을 수 없습니다. Docker를 먼저 설치·실행해주세요.")

    kor = TESSDATA_DIR / "kor.traineddata"
    if not kor.exists():
        sys.exit(
            f"{kor.relative_to(REPO_ROOT)} 가 없습니다. "
            "먼저 `bash ocr/fetch_tessdata.sh` 를 실행해주세요."
        )


def list_captures() -> list[Path]:
    """OCR 대상 PNG 목록을 파일명 순으로 반환한다.

    Returns:
        ``data/captures/`` 안의 PNG 경로 목록(정렬됨).
    """
    return sorted(CAPTURE_DIR.glob("*.png"))


def run_one(image_path: Path, lang: str) -> OcrResult:
    """PNG 한 장을 컨테이너에서 OCR 처리하고 텍스트를 저장한다.

    Args:
        image_path: 입력 PNG의 절대 경로.
        lang: tesseract ``-l`` 인자(예: ``kor+eng``).

    Returns:
        결과 요약이 담긴 ``OcrResult``.
    """
    rel_in = image_path.relative_to(REPO_ROOT).as_posix()
    # tesseract는 출력 인자에 확장자를 붙이지 않는다(.txt 를 스스로 붙인다).
    out_stem = OUTPUT_DIR / image_path.stem
    rel_out_stem = out_stem.relative_to(REPO_ROOT).as_posix()

    command = [
        "docker", "run", "--rm",
        "-v", f"{REPO_ROOT}:{WORKDIR_IN_CONTAINER}",
        "-w", WORKDIR_IN_CONTAINER,
        # 이미지 기본 tessdata 대신 저장소의 tessdata를 쓰게 한다.
        "-e", f"TESSDATA_PREFIX={WORKDIR_IN_CONTAINER}/ocr/tessdata",
        OCR_IMAGE,
        rel_in, rel_out_stem,
        "-l", lang,
    ]

    print(f"[ocr ] {rel_in} (-l {lang})", flush=True)
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command, capture_output=True, text=True, timeout=OCR_TIMEOUT_SEC
        )
    except subprocess.TimeoutExpired:
        return OcrResult(
            image=rel_in, text_file=None, ok=False, lang=lang,
            error=f"{OCR_TIMEOUT_SEC}초 안에 끝나지 않음",
        )
    elapsed = round(time.monotonic() - started, 2)

    if proc.returncode != 0:
        reason = (proc.stderr or proc.stdout).strip().splitlines()
        return OcrResult(
            image=rel_in, text_file=None, ok=False, lang=lang, elapsed_sec=elapsed,
            error=reason[-1] if reason else f"exit code {proc.returncode}",
        )

    text_path = out_stem.with_suffix(".txt")
    text = text_path.read_text(encoding="utf-8")
    result = OcrResult(
        image=rel_in,
        text_file=text_path.relative_to(REPO_ROOT).as_posix(),
        ok=True,
        lang=lang,
        chars=len(text),
        non_empty_lines=sum(1 for line in text.splitlines() if line.strip()),
        hangul_chars=len(HANGUL_RE.findall(text)),
        ascii_letter_chars=len(ASCII_LETTER_RE.findall(text)),
        elapsed_sec=elapsed,
    )
    print(
        f"[ok  ] {result.text_file} "
        f"{result.chars}자 / 한글 {result.hangul_chars}자 / "
        f"{result.non_empty_lines}줄 / {elapsed}초",
        flush=True,
    )
    return result


def write_log(results: list[OcrResult], lang: str) -> Path:
    """실행 요약을 JSON으로 남긴다.

    Args:
        results: OCR 결과 목록.
        lang: 사용한 언어 조합.

    Returns:
        기록한 로그 파일 경로.
    """
    log_path = OUTPUT_DIR / "ocr_run.json"
    payload = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "image": OCR_IMAGE,
        "lang": lang,
        "tessdata_source": (
            "https://github.com/tesseract-ocr/tessdata_best (kor, eng)"
        ),
        "results": [asdict(r) for r in results],
    }
    log_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return log_path


def main() -> int:
    """CLI 진입점.

    Returns:
        하나라도 성공하면 0, 대상이 없거나 전부 실패하면 1.
    """
    parser = argparse.ArgumentParser(description="캡처 PNG에 대한 컨테이너 OCR 실행")
    parser.add_argument(
        "--lang", default="kor+eng",
        help="tesseract 언어 조합 (기본: kor+eng)",
    )
    args = parser.parse_args()

    ensure_prerequisites()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = list_captures()
    if not images:
        print(
            f"[warn] {CAPTURE_DIR.relative_to(REPO_ROOT)} 에 PNG가 없습니다. "
            "캡처 단계를 먼저 실행해주세요.",
            file=sys.stderr,
        )
        return 1

    results = [run_one(path, args.lang) for path in images]
    log_path = write_log(results, args.lang)

    ok_count = sum(1 for r in results if r.ok)
    print(
        f"\n[요약] 성공 {ok_count}건 / 전체 {len(results)}건, "
        f"로그: {log_path.relative_to(REPO_ROOT).as_posix()}",
        flush=True,
    )
    return 0 if ok_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
