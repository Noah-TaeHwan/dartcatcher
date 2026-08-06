#!/usr/bin/env bash
#
# 파이프라인 전체(크롤 → 캡처 → OCR)를 순서대로 한 번 실행한다.
#
#   1단계 크롤   : crawl4ai 컨테이너(REST API)로 DART 공시 목록을 마크다운으로 수집
#   2단계 캡처   : Playwright 컨테이너로 같은 사이트의 렌더링 화면을 PNG로 저장
#   3단계 OCR    : tesseract 컨테이너로 PNG에서 텍스트를 추출
#
# 세 단계 모두 호스트에 런타임을 설치하지 않고 컨테이너 안에서만 돌린다.
# 호스트에 필요한 것은 docker, bash, python3(표준 라이브러리), curl 뿐이다.
#
# 사용법:
#   bash run_pipeline.sh                  # 3단계 모두 실행
#   bash run_pipeline.sh --stop-crawler   # 끝나고 crawl4ai 컨테이너까지 정리
#   bash run_pipeline.sh --skip-crawl     # 이미 수집한 결과가 있을 때 2·3단계만
#   bash run_pipeline.sh --cleanup        # 끝나고 오래된 data/ 산출물도 정리
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# --- 고정 값 -----------------------------------------------------------------

# 이미지 태그는 모두 고정한다. latest가 조용히 올라가면 결과 재현이 깨지기 때문이다.
# (crawl4ai만 예외 — 이 이미지는 버전 태그를 제공하지 않아 latest를 쓴다.)
CRAWLER_IMAGE="unclecode/crawl4ai:latest"
CAPTURE_IMAGE="mcr.microsoft.com/playwright/python:v1.62.0-noble"
OCR_IMAGE="jitesoft/tesseract-ocr:5.5.2"

CRAWLER_CONTAINER="crawl4ai-pipeline"
CRAWLER_PORT="11235"
CRAWLER_BASE_URL="http://localhost:${CRAWLER_PORT}"

# 캡처 컨테이너에서 설치할 playwright 파이썬 패키지 버전.
# 이미지에는 브라우저 바이너리만 있고 pip 패키지가 없어 실행 시 설치가 필요하다.
# 이미지 태그와 같은 버전으로 맞춰 런타임/라이브러리 불일치를 막는다.
PLAYWRIGHT_PKG_VERSION="1.62.0"

# crawl4ai 헬스체크 최대 대기 시간(초).
HEALTH_TIMEOUT_SEC=120

STOP_CRAWLER=0
SKIP_CRAWL=0

# 산출물 보관 정책: data/captures·data/ocr 에 최신 KEEP_RUNS 회 실행만 남긴다.
# 자세한 규칙과 사용법은 tools/retain_outputs.sh 참고.
KEEP_RUNS=3
CLEANUP=0

# --- 인자 파싱 ---------------------------------------------------------------

for arg in "$@"; do
  case "$arg" in
    --stop-crawler) STOP_CRAWLER=1 ;;
    --skip-crawl)   SKIP_CRAWL=1 ;;
    --cleanup)      CLEANUP=1 ;;
    -h|--help)      sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "알 수 없는 인자: $arg (사용법은 --help)" >&2; exit 2 ;;
  esac
done

# --- 공용 함수 ---------------------------------------------------------------

# 단계 구분선을 출력한다. $1 = 표시할 제목
step() {
  echo
  echo "════════════════════════════════════════════════════════════"
  echo "  $1"
  echo "════════════════════════════════════════════════════════════"
}

# 필수 명령이 없으면 즉시 중단한다. $1 = 명령 이름
require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[중단] '$1' 명령을 찾을 수 없습니다. 설치 후 다시 실행해주세요." >&2
    exit 1
  }
}

# crawl4ai API 토큰을 준비한다.
# .env가 없으면 새로 만들어 넣는다. .env는 gitignore 대상이라 저장소에 올라가지 않는다.
ensure_token() {
  if [[ ! -f .env ]]; then
    echo "[준비] .env가 없어 새 API 토큰을 생성한다."
    printf 'CRAWL4AI_API_TOKEN=%s\n' "$(openssl rand -hex 32)" > .env
    chmod 600 .env
  fi
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a

  if [[ -z "${CRAWL4AI_API_TOKEN:-}" ]]; then
    echo "[중단] .env에서 CRAWL4AI_API_TOKEN을 읽지 못했습니다." >&2
    exit 1
  fi
}

# crawl4ai 컨테이너가 응답할 때까지 /health를 폴링한다.
wait_for_crawler() {
  local waited=0
  until curl -sf -H "Authorization: Bearer ${CRAWL4AI_API_TOKEN}" \
        "${CRAWLER_BASE_URL}/health" >/dev/null 2>&1; do
    if (( waited >= HEALTH_TIMEOUT_SEC )); then
      echo "[중단] ${HEALTH_TIMEOUT_SEC}초 안에 crawl4ai가 응답하지 않았습니다." >&2
      docker logs --tail 30 "$CRAWLER_CONTAINER" >&2 || true
      exit 1
    fi
    sleep 2
    waited=$(( waited + 2 ))
  done
  echo "[확인] crawl4ai 응답 정상 ($(curl -sf \
    -H "Authorization: Bearer ${CRAWL4AI_API_TOKEN}" "${CRAWLER_BASE_URL}/health"))"
}

# --- 0단계: 사전 확인 --------------------------------------------------------

step "0/3  사전 확인"
require_command docker
require_command python3
require_command curl
docker info >/dev/null 2>&1 || {
  echo "[중단] Docker 데몬에 연결할 수 없습니다. Docker를 실행해주세요." >&2
  exit 1
}
echo "[확인] docker $(docker --version | awk '{print $3}' | tr -d ,) / python3 $(python3 -V | awk '{print $2}')"

# --- 1단계: 크롤 -------------------------------------------------------------

if (( SKIP_CRAWL )); then
  step "1/3  크롤 (--skip-crawl 지정으로 건너뜀)"
else
  step "1/3  크롤  ($CRAWLER_IMAGE)"
  require_command openssl
  ensure_token

  if [[ -n "$(docker ps -q -f "name=^${CRAWLER_CONTAINER}$")" ]]; then
    echo "[재사용] 컨테이너 ${CRAWLER_CONTAINER} 가 이미 실행 중이다."
  else
    # 중지 상태로 남아 있는 동명 컨테이너가 있으면 지우고 새로 띄운다.
    docker rm -f "$CRAWLER_CONTAINER" >/dev/null 2>&1 || true
    echo "[기동] ${CRAWLER_CONTAINER} (포트 ${CRAWLER_PORT})"
    # GUNICORN_BIND: 이미지 기본값이 127.0.0.1 이라 호스트에서 접속되지 않는다.
    # 비루프백으로 열려면 이미지가 API 토큰을 요구하므로 함께 넘긴다.
    # --shm-size=1g: Chromium이 기본 64MB 공유메모리에서 죽는 것을 막는다.
    docker run -d --name "$CRAWLER_CONTAINER" \
      -p "${CRAWLER_PORT}:${CRAWLER_PORT}" \
      --shm-size=1g \
      -e GUNICORN_BIND="0.0.0.0:${CRAWLER_PORT}" \
      -e CRAWL4AI_API_TOKEN="$CRAWL4AI_API_TOKEN" \
      "$CRAWLER_IMAGE" >/dev/null
  fi

  wait_for_crawler
  # crawl_dart.py 는 페이지 사이에 2.5초씩 쉬며 1~3페이지만 수집한다.
  CRAWL4AI_BASE_URL="$CRAWLER_BASE_URL" python3 crawler/crawl_dart.py
fi

# --- 2단계: 캡처 -------------------------------------------------------------

step "2/3  캡처  ($CAPTURE_IMAGE)"
# 저장소를 /work 로 마운트해 PNG가 호스트의 data/captures/ 에 그대로 떨어지게 한다.
docker run --rm \
  -v "$REPO_ROOT":/work -w /work \
  "$CAPTURE_IMAGE" \
  bash -c "pip install --quiet --root-user-action=ignore playwright==${PLAYWRIGHT_PKG_VERSION} \
           && python capture/capture.py"

# --- 3단계: OCR --------------------------------------------------------------

step "3/3  OCR  ($OCR_IMAGE)"
# 한국어 학습 데이터가 없으면 받아온다(이미 있으면 건너뛴다).
bash ocr/fetch_tessdata.sh
python3 ocr/run_ocr.py

# --- 마무리 ------------------------------------------------------------------

step "완료"
echo "산출물:"
echo "  크롤 : $(find data/crawl -maxdepth 1 -name '*.md' -type f 2>/dev/null | wc -l | tr -d ' ')개 마크다운  (data/crawl/)"
echo "  캡처 : $(find data/captures -maxdepth 1 -name '*.png' -type f 2>/dev/null | wc -l | tr -d ' ')개 PNG        (data/captures/)"
echo "  OCR  : $(find data/ocr -maxdepth 1 -name '*.txt' -type f 2>/dev/null | wc -l | tr -d ' ')개 텍스트     (data/ocr/)"

# 산출물 보관 정책: 기본은 dry-run으로 안내만, --cleanup 일 때만 실제로 정리한다.
echo
if (( CLEANUP )); then
  echo "[정리] 오래된 산출물(최신 ${KEEP_RUNS}회 실행만 유지)"
  tools/retain_outputs.sh --keep "${KEEP_RUNS}" --delete
else
  echo "산출물 보관: 최신 ${KEEP_RUNS}회 실행만 유지한다. 오래된 것은 아래로 정리한다:"
  echo "  tools/retain_outputs.sh --keep ${KEEP_RUNS} --delete   # dry-run 후 실제 정리는 --delete"
  echo "  bash run_pipeline.sh --cleanup                         # 파이프라인 끝나고 정리까지"
fi

if (( STOP_CRAWLER )); then
  echo
  echo "[정리] ${CRAWLER_CONTAINER} 제거"
  docker rm -f "$CRAWLER_CONTAINER" >/dev/null 2>&1 || true
else
  echo
  echo "crawl4ai 컨테이너는 계속 떠 있다. 정리하려면:"
  echo "  docker rm -f ${CRAWLER_CONTAINER}"
fi
