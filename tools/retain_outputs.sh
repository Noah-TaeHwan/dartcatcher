#!/usr/bin/env bash
#
# data/ 의 재실행 누적 산출물을 최신 N회 실행만 남기고 정리·보관한다.
#
# 배경
#   캡처(capture/)와 OCR(ocr/) 단계는 실행할 때마다 타임스탬프 접두어를 앞에 붙인
#   산출물을 data/captures/, data/ocr/ 에 쌓는다. README "품질과 한계" 절에 적어둔
#   대로 예전에는 정리·보관 정책이 없어 재실행할 때마다 파일이 계속 늘어났다.
#   이 스크립트가 그 규칙을 코드로 구현한다.
#
# 실행(run) 식별
#   파일명 앞의 `<YYYYMMDDTHHMMSSZ>`(UTC)가 곧 실행 키다. 같은 실행이 만든 파일
#   (data/captures 의 <stamp>_run.json·<stamp>_*.png, data/ocr 의 <stamp>_*.txt)
#   은 이 접두어를 공유한다. 고정 길이·UTC라 사전순 정렬이 곧 시간순이다.
#   가장 오래된 실행부터 정리해 최신 N회만 남긴다.
#   타임스탬프가 없는 메타데이터(ocr_run.json 등)는 대상이 아니다.
#   크롤(crawl/)은 파일명에 타임스탬프가 없어(덮어씀) 재실행 누적이 없으므로 제외한다.
#
# 안전 장치
#   기본은 dry-run이라 아무것도 바꾸지 않고 대상만 나열한다. 실제 변경은
#   --delete(삭제) 또는 --archive <DIR>(백업으로 이동)를 명시했을 때만 수행한다.
#
# 사용법
#   tools/retain_outputs.sh                    # dry-run(기본): 대상 목록만 출력
#   tools/retain_outputs.sh --keep 5           # 최신 5회만 유지(기본 3)
#   tools/retain_outputs.sh --delete           # 오래된 산출물을 실제 삭제
#   tools/retain_outputs.sh --archive BACKUP   # 삭제 대신 BACKUP/ 로 이동(백업)
#   tools/retain_outputs.sh --help             # 도움말
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- 기본값 ----------------------------------------------------------------

KEEP=3         # 유지할 최신 실행 수
MODE="dry"     # dry | delete | archive
ARCHIVE_DIR="" # --archive 로 지정한 백업 디렉터리(루트 기준 상대 경로)

# 정리 대상 디렉터리.
READ_DIRS=(data/captures data/ocr)

# --- 인자 파싱 -------------------------------------------------------------

usage() {
  # 맨 앞의 주석 블록(2행부터 "set -euo pipefail" 직전까지)만 도움말로 출력한다.
  awk 'NR >= 2 { if ($0 ~ /^set -euo pipefail/) exit; print }' "$0"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep)
      if [[ $# -lt 2 ]]; then
        echo "[오류] --keep 에는 유지할 실행 수를 주세요." >&2
        exit 2
      fi
      KEEP="$2"
      shift 2
      ;;
    --delete) MODE="delete"; shift ;;
    --archive)
      if [[ $# -lt 2 ]]; then
        echo "[오류] --archive 에는 백업 디렉터리를 주세요." >&2
        exit 2
      fi
      MODE="archive"; ARCHIVE_DIR="$2"
      shift 2
      ;;
    --dry-run) MODE="dry"; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "[오류] 알 수 없는 인자: $1 (사용법: $0 --help)" >&2
      exit 2
      ;;
  esac
done

if [[ ! "$KEEP" =~ ^[0-9]+$ ]] || (( KEEP < 1 )); then
  echo "[오류] --keep 은 1 이상의 정수여야 합니다 (받은 값: '$KEEP')." >&2
  exit 2
fi

if [[ "$MODE" == "archive" && -z "$ARCHIVE_DIR" ]]; then
  echo "[오류] --archive 에는 백업 디렉터리가 필요합니다." >&2
  exit 2
fi

# --- 함수 ------------------------------------------------------------------

# 한 디렉터리에 존재하는 실행 접두어(타임스탬프) 목록을 중복 없이 출력한다.
stamps_in_dir() {
  local dir="$1" f stamp
  shopt -s nullglob
  for f in "$dir"/*; do
    stamp="$(basename "$f")"
    if [[ "$stamp" =~ ^([0-9]{8}T[0-9]{6}Z)_ ]]; then
      printf '%s\n' "${BASH_REMATCH[1]}"
    fi
  done
  shopt -u nullglob
}

# --- 본문 ------------------------------------------------------------------

echo "산출물 보관 정책: 최신 ${KEEP}회 실행만 유지 (MODE=${MODE})"
echo "대상: ${READ_DIRS[*]}"
echo

total_targets=0

for dir in "${READ_DIRS[@]}"; do
  [[ -d "$dir" ]] || { echo "[skip] $dir 없음"; continue; }

  stamps=()
  while IFS= read -r s; do
    stamps+=("$s")
  done < <(stamps_in_dir "$dir" | sort -u)
  if (( ${#stamps[@]} == 0 )); then
    echo "[skip] $dir : 타임스탬프 산출물 없음"
    continue
  fi

  echo "── $dir ──"
  echo "  실행 ${#stamps[@]}회 → 최신 ${KEEP}회 유지"

  if (( ${#stamps[@]} <= KEEP )); then
    echo "  정리 대상 없음 (전부 유지)"
    continue
  fi

  # 오래된 것부터 전체에서 최신 KEEP 개를 뺀 개수가 정리 대상 실행 수다.
  remove_count=$(( ${#stamps[@]} - KEEP ))

  echo "  유지(최신):"
  for (( i = remove_count; i < ${#stamps[@]}; i++ )); do
    echo "    ${stamps[i]}"
  done

  echo "  정리 대상(오래된 ${remove_count}회):"
  shopt -s nullglob
  for (( i = 0; i < remove_count; i++ )); do
    for f in "$dir/${stamps[i]}"_*; do
      echo "    ${f}"
      case "$MODE" in
        delete)   rm -f -- "$f" ;;
        archive)  mkdir -p "$ARCHIVE_DIR"; mv -f -- "$f" "$ARCHIVE_DIR/" ;;
      esac
      total_targets=$(( total_targets + 1 ))
    done
  done
  shopt -u nullglob
  echo
done

echo "=== 요약 ==="
echo "대상(정리할) 파일: ${total_targets}"
echo "동작: ${MODE}"

if [[ "$MODE" == "dry" ]]; then
  echo "※ dry-run입니다. 실제로 정리하려면 --delete(--archive)를 붙여 재실행하세요."
fi
