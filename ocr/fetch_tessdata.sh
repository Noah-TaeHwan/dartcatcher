#!/usr/bin/env bash
# 한국어·영어 OCR 학습 데이터(traineddata)를 ocr/tessdata/ 로 내려받는다.
#
# jitesoft/tesseract-ocr 이미지에는 eng/equ/osd 세 가지 언어만 들어 있어
# 한국어(kor)를 인식하려면 학습 데이터를 따로 받아 컨테이너에 마운트해야 한다.
# 파일이 이미 있으면 다시 받지 않는다(멱등).
#
# 출처: tesseract-ocr 공식 조직의 tessdata_best 저장소 (Apache-2.0)
#   https://github.com/tesseract-ocr/tessdata_best
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESSDATA_DIR="$REPO_ROOT/ocr/tessdata"

# tessdata_best: LSTM 최고 정확도 모델. 속도 대신 정확도를 택했다.
BASE_URL="https://github.com/tesseract-ocr/tessdata_best/raw/main"

# kor = 한국어, eng = 영어(-l kor+eng 로 함께 쓰므로 같은 저장소 버전으로 맞춘다)
LANGS=(kor eng)

mkdir -p "$TESSDATA_DIR"

for lang in "${LANGS[@]}"; do
  target="$TESSDATA_DIR/$lang.traineddata"
  if [[ -s "$target" ]]; then
    echo "[skip] $lang.traineddata 이미 존재 ($(wc -c <"$target" | tr -d ' ') bytes)"
    continue
  fi
  echo "[get ] $BASE_URL/$lang.traineddata"
  curl -sSL --fail -o "$target" "$BASE_URL/$lang.traineddata"
  echo "[ok  ] $lang.traineddata ($(wc -c <"$target" | tr -d ' ') bytes)"
done
