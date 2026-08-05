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
