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
- [ ] `shellcheck run_pipeline.sh ocr/fetch_tessdata.sh` 통과
- [ ] 문서의 수치를 바꿨다면, 그 수치가 나온 실행 출력을 `evidence/` 에 함께 넣었다
- [ ] 크롤링 대상을 늘렸다면, `robots.txt` 판단 근거와 요청 간격을 적었다
- [ ] 인증키나 토큰이 diff에 들어가지 않았다
