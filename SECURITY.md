# 보안 정책

## 인증키 취급

이 저장소는 두 종류의 비밀값을 쓴다. 둘 다 저장소에 커밋하지 않는다.

| 값 | 용도 | 보관 |
| --- | --- | --- |
| `CRAWL4AI_API_TOKEN` | crawl4ai 컨테이너 인증 | `.env` (`.gitignore` 대상). `run_pipeline.sh` 가 없으면 만든다 |
| `API_K_DART` | DART 공식 OpenAPI 인증키 | 셸 환경변수로만. `.env` 에도 쓰지 않는다 |

`API_K_DART` 를 `.env` 에 두지 않는 이유는, 이 저장소의 `.env` 가 crawl4ai 토큰
전용이고 키 파일이 하나 늘면 실수로 커밋할 표면도 늘기 때문이다.

`api/` 의 두 스크립트 중 인증키를 실제로 다루는 것은 `fetch_disclosures.py`
하나뿐이다. 이 스크립트는 인증키를 로그에 찍지 않는다. 요청 주소를 출력할 때
`crtfc_key` 자리를 `***` 로 바꾸고, HTTP 오류가 나도 마스킹한 주소만 남긴다.
산출물 JSON에 저장하는 `request_url` 도 마스킹된 형태다.

`cross_check.py` 는 인증키를 아예 건드리지 않는다. 환경변수를 읽지 않고
네트워크 요청도 하지 않으며 `fetch_disclosures.py` 가 미리 받아 디스크에
저장해 둔 JSON만 읽는다.

기여할 때 `fetch_disclosures.py` 의 키를 다루는 코드를 건드린다면 이 성질이
유지되는지 확인한다.

## 취약점 신고

키가 로그나 산출물에 새는 경로를 발견했거나 다른 보안 문제를 찾았다면 공개
이슈로 열지 말고 저장소 소유자에게 GitHub의
[Private vulnerability reporting](https://github.com/Noah-TaeHwan/dartcatcher/security/advisories/new)
으로 알려주기 바란다.

## 지원 범위

이 저장소는 동작 검증용 예제이며 운영 환경을 위한 것이 아니다. 버전 지원 정책은
두지 않는다. 최신 `main` 을 기준으로 대응한다.
