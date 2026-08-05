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
- `tools/check_links.py`: 문서 상대 링크와 앵커 검사기. 파일 간 앵커 참조와
  중첩된 이미지 배지 링크의 바깥쪽 target까지 검증한다
- `ruff.toml`: lint 검사 범위를 임포트·문장·문법 오류·미사용 심볼(E4/E7/E9/F)로
  좁힌 설정
- `.github/workflows/ci.yml`: lint(ruff, shellcheck)·docs(링크·앵커)·evidence
  (README 수치 대조) 3잡 CI 워크플로
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`: 기여 안내, 보안 정책,
  행동강령
- `.github/ISSUE_TEMPLATE/`: 버그 신고·개선 제안 양식과 이슈 생성 진입 설정
  3개 파일. `.github/pull_request_template.md`: PR 템플릿
- README에 "당신이 여기 왔다면" 입구 분기표와 CI 상태 배지 추가

### 수정

- `run_pipeline.sh`: shellcheck 지적을 해소했다. `set -a; . ./.env; set +a`
  한 줄에 붙어 있던 SC1091 disable 주석이 소스 명령이 아니라 앞선 `set -a`에
  붙어 무시되고 있었다. 세 줄로 나누고 주석을 소스 줄 바로 위로 옮겨 실제로
  적용되게 했다. 완료 요약의 산출물 개수 집계도 `ls`에서 `find`로 바꿔
  SC2012를 함께 해소했다

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
