# OCR (tesseract / Docker)

캡처된 화면 PNG에서 텍스트를 뽑아내는 단계. 파이프라인의 마지막 층이다.
호스트에는 tesseract를 설치하지 않고 컨테이너로만 실행한다.

## 왜 `jitesoft/tesseract-ocr` 인가

tesseract는 공식 Docker 이미지를 배포하지 않는다. 그래서 서드파티 이미지 중에서 골라야 했다.

| 후보 | 판단 |
| --- | --- |
| **jitesoft/tesseract-ocr** (채택) | tesseract 5.5.2 최신 계열을 따라가고, `5.5.2` 처럼 패치 단위까지 고정할 수 있는 태그를 제공한다. 태그가 71개로 이력이 길어 유지보수가 이어지고 있음을 확인했다(2026-07-30 갱신). arm64/amd64 멀티아치라 애플 실리콘에서 에뮬레이션 없이 돈다. |
| `tesseractshadow/tesseract4re` | tesseract 4 계열에 머물러 있다. 한국어 인식률이 5.x의 LSTM 엔진보다 낮다. |
| 직접 Dockerfile 작성 | `apt-get install tesseract-ocr-kor` 로 만들 수 있지만, 이 프로젝트는 "검증된 이미지를 조합한다"는 방침이라 이미지를 새로 굽지 않았다. 배포판 패키지는 tesseract 버전이 뒤처지는 문제도 있다. |

### 이미지 정보 (실측)

```bash
$ docker pull jitesoft/tesseract-ocr:5.5.2
Digest: sha256:23fbc1f29a6d35e9c4bd1a8206a7c4f73d48a3cc3bcc33c579e92c47e0d52f76
Status: Downloaded newer image for jitesoft/tesseract-ocr:5.5.2

$ docker images jitesoft/tesseract-ocr --format '{{.Tag}} {{.ID}} {{.Size}}'
5.5.2 23fbc1f29a6d 387MB

$ docker image inspect jitesoft/tesseract-ocr:5.5.2 --format '{{.Os}}/{{.Architecture}} {{.Size}}'
linux/arm64 123266647
```

크기가 두 값으로 보고된다. `docker images` 는 **387MB**, `docker image inspect` 의
`.Size` 는 약 **123MB** 다. 어느 쪽이 디스크 실사용량인지는 확인하지 못했으므로
두 출력을 그대로 남긴다(크롤러 이미지에서도 같은 차이가 있었다).

기반 OS는 Ubuntu 22.04.2 LTS, tesseract는 5.5.2 / leptonica 1.87.0 이다.

## 한국어 학습 데이터(traineddata)

이미지에 들어 있는 언어는 **eng / equ / osd 세 가지뿐**이다. 한국어가 없다.

```bash
$ docker run --rm jitesoft/tesseract-ocr:5.5.2 --list-langs
List of available languages in "/usr/local/share/tessdata/" (3):
eng
equ
osd
```

그래서 한국어 모델을 따로 받아 컨테이너에 마운트한다.

### 출처

tesseract-ocr 공식 GitHub 조직의 **tessdata_best** 저장소에서 받는다.

- 저장소: <https://github.com/tesseract-ocr/tessdata_best>
- 한국어: <https://github.com/tesseract-ocr/tessdata_best/raw/main/kor.traineddata>
- 영어: <https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata>
- 라이선스: Apache-2.0

`tessdata`(기본), `tessdata_fast`(속도 우선), `tessdata_best`(정확도 우선) 세 종류 중
**`tessdata_best`** 를 골랐다. 이 파이프라인은 배치로 도는 수집기라 장당 몇십 초 차이보다
인식 정확도가 중요하다고 판단했다.

영어(`eng`)도 함께 받는 이유는 `-l kor+eng` 로 두 언어를 같이 쓰는데,
`TESSDATA_PREFIX` 를 저장소 쪽으로 돌리면 이미지 내장 `eng` 를 더 이상 찾지 못하기 때문이다.
같은 저장소 버전으로 맞춰야 조합이 일관된다.

### 내려받기

```bash
bash ocr/fetch_tessdata.sh
```

실제 출력:

```
[get ] https://github.com/tesseract-ocr/tessdata_best/raw/main/kor.traineddata
[ok  ] kor.traineddata (12528128 bytes)
[get ] https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata
[ok  ] eng.traineddata (15400601 bytes)
```

| 파일 | 크기 | SHA-256 |
| --- | --- | --- |
| `kor.traineddata` | 12,528,128 B | `f888d4038348a0c3d25151e7f452bda0d74ca275b18cab146798bcbb94084fff` |
| `eng.traineddata` | 15,400,601 B | `8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba` |

두 파일 합계 약 27MB는 `.gitignore` 대상이다. 저장소에 바이너리를 넣는 대신
스크립트로 받게 했고 스크립트는 이미 있으면 다시 받지 않는다.

## 실행

### 스크립트로 전부

```bash
python3 ocr/run_ocr.py
```

`data/captures/*.png` 를 하나씩 컨테이너에 넣어 `-l kor+eng` 로 처리하고
`data/ocr/` 에 텍스트와 실행 로그(`ocr_run.json`)를 남긴다.

### 컨테이너를 직접 호출할 때

```bash
docker run --rm \
  -v "$(pwd)":/work -w /work \
  -e TESSDATA_PREFIX=/work/ocr/tessdata \
  jitesoft/tesseract-ocr:5.5.2 \
  data/captures/20260805T003628Z_dart-search.png data/ocr/dart-search -l kor+eng
```

- `TESSDATA_PREFIX` 를 `/work/ocr/tessdata` 로 덮어써야 한국어 모델을 찾는다.
  이미지 기본값은 `/usr/local/share/tessdata` 이고 거기엔 `kor` 이 없다.
- tesseract는 출력 인자에 확장자를 붙이지 않는다. `data/ocr/dart-search` 를 주면
  `data/ocr/dart-search.txt` 가 생긴다.

## 실제 실행 출력 (증거)

```
[ocr ] data/captures/20260805T003628Z_dart-main.png (-l kor+eng)
[ok  ] data/ocr/20260805T003628Z_dart-main.txt 4184자 / 한글 913자 / 58줄 / 40.31초
[ocr ] data/captures/20260805T003628Z_dart-search.png (-l kor+eng)
[ok  ] data/ocr/20260805T003628Z_dart-search.txt 1695자 / 한글 437자 / 47줄 / 23.23초
[ocr ] data/captures/20260805T003749Z_quotes-toscrape.png (-l kor+eng)
[ok  ] data/ocr/20260805T003749Z_quotes-toscrape.txt 1377자 / 한글 1자 / 42줄 / 11.98초
[ocr ] data/captures/20260805T010849Z_dart-main.png (-l kor+eng)
[ok  ] data/ocr/20260805T010849Z_dart-main.txt 4052자 / 한글 893자 / 52줄 / 43.08초
[ocr ] data/captures/20260805T010849Z_dart-search.png (-l kor+eng)
[ok  ] data/ocr/20260805T010849Z_dart-search.txt 1695자 / 한글 437자 / 47줄 / 23.03초

[요약] 성공 5건 / 전체 5건, 로그: data/ocr/ocr_run.json
```

전체 페이지 캡처는 세로로 길어 장당 12~43초가 걸린다(1444×2469 기준 약 40초).

## OCR 품질 평가

눈대중 대신 정답지와 대조해 숫자로 측정했다.

### 영어: 사실상 완벽

폴백 대상인 `quotes.toscrape.com` 은 정적 사이트라 원본 HTML을 정답으로 쓸 수 있다.
원본에서 인용문과 저자명을 뽑아 OCR 결과와 **문자 단위 완전 일치**를 확인했다.

| 항목 | 결과 |
| --- | --- |
| 인용문 | **10/10 완전 일치** |
| 저자명 | **8/8 완전 일치** |

### 한국어: 61.3%, 본문은 읽히고 UI 조각은 깨진다

`ocr/reference/dart-search_labels.txt` 에 캡처 PNG를 직접 눈으로 읽어 옮긴 한국어
문자열 62개를 정답지로 두고 대조했다. 공백 차이는 무시한다(OCR이 표 레이아웃 때문에
공백을 임의로 넣고 빼기 때문).

```bash
$ python3 ocr/eval_quality.py
[결과] 정확 일치 38/62 (61.3%)
```

**잘 읽은 쪽**은 길이가 있는 본문·문장이다(모두 OCR 결과 원문 그대로).

```
조회 결과가 없습니다.
한국거래소 코스닥시장본부 소관
개인정보 처리방침 ㅣ 정보이용시 유의사항 ㅣ 보고서정보 ㅣ 055서비스
※ [:검색구분]을 조정하면 본문내용 등 다양한 조건으로 검색이 가능합니다.
공시통합검색                          A> 공시서류검색 > 공시통합검색
```

문장이라도 **앞머리가 색 배지에 붙어 있으면 그 부분만 깨진다.** 예를 들어
`제출 후 정정신고가 있으니 관련 보고서를 참조` 는 앞의 `정` 배지와 뭉쳐 이렇게 나왔다:

```
설명 | [Gres 정정신고가 있으니 관련 보고서를 참조    [B) 한국거래소 유가증권시장본부 소관
```

뒷부분(`정정신고가 있으니 관련 보고서를 참조`)은 정확한데 `제출 후` 가 `[Gres` 로 뭉개졌다.
정확도 측정에서는 이런 항목도 불일치로 센다.

**틀린 쪽**은 짧은 UI 조각, 색 배지 안의 글자, 체크박스 라벨이다.

| 정답 | OCR | 위치 |
| --- | --- | --- |
| 종목코드 | `증목코드` | 상단 검색바(28행). 같은 문구가 29행에서는 정확히 읽혔다 |
| 회사명 | `획사명` | 상세검색 폼 라벨(29행) |
| 코넥스시장 | `[« 29스시장` | 범례의 색 배지(37행) |
| 기타법인 | `[5 기타비인` | 범례의 색 배지(37행) |
| 금융위원회 | `8) 38위원회` | 푸터 로고 옆(42행) |
| 공정거래위원회 | `6) 궁정거래위원회` | 푸터 로고 옆(42행) |
| RSS서비스 | `055서비스` | 푸터 링크(43행) |
| 서울특별시 | `서물특별시` | 푸터 주소(44행) |
| 자산유동화 | `자산유통화` | 공시유형 체크박스 |
| 발행공시 | (해당 조각 없음) | 공시유형 체크박스 |
| 철회보고서 | (해당 조각 없음) | 범례의 색 배지 |

정리하면 **읽을거리로서의 본문은 쓸 만하고, 화면 UI 라벨은 신뢰할 수 없다.**
숫자·날짜(`2026.08.05`)와 회사명 같은 굵은 본문 텍스트는 대체로 살아남지만,
아이콘 옆 작은 글자나 색 배지 위의 흰 글자는 자주 깨진다. 이 결과를 그대로 하류
분석에 쓰기는 어렵고 사람이 확인하는 보조 자료 정도가 적절하다.

### 원인과 개선: 캡처 해상도가 지배적이다

tesseract가 입력 이미지의 해상도를 `Estimating resolution as 153` 으로 추정했다.
tesseract는 300 DPI 부근에서 가장 잘 동작하는데, 웹 스크린샷은 그 절반 수준이다.

가설을 확인하려고 같은 페이지를 `device_scale_factor=2` 로 다시 캡처해
(1444×1252 → 2888×2504) 같은 정답지로 재측정했다.

```
$ python3 ocr/eval_quality.py --ocr-text evidence/ocr_hidpi_sample.txt
[결과] 정확 일치 52/62 (83.9%)
```

**61.3% → 83.9%.** 전처리나 모델 교체 없이 캡처 해상도만 2배로 올려 얻은 수치다.
`Estimating resolution` 도 153 → 261 로 올라갔다. 다만 이 실험은 `dart-search` 한
페이지에 대해 1회 측정한 것이라, 다른 페이지에서도 같은 폭으로 개선되는지는 **미검증**이다.

이 결과는 루트 README의 로드맵에 "캡처 단계 `device_scale_factor` 상향"으로 반영했다.
현재 파이프라인 기본값은 아직 1배다.

## 파일

| 경로 | 내용 |
| --- | --- |
| `ocr/fetch_tessdata.sh` | 학습 데이터 내려받기(멱등) |
| `ocr/run_ocr.py` | 캡처 PNG 일괄 OCR 실행 |
| `ocr/eval_quality.py` | 정답지 대조 정확도 측정 |
| `ocr/reference/dart-search_labels.txt` | 손으로 옮긴 정답지 62건 |
| `ocr/tessdata/*.traineddata` | 학습 데이터(gitignore 대상) |
| `data/ocr/*.txt` | 추출된 텍스트 |
| `data/ocr/ocr_run.json` | 실행 로그(문자 수, 한글 수, 소요 시간) |
| `evidence/ocr_run.txt` | 실행 출력 원문 |
| `evidence/ocr_quality.txt` | 한국어 정확도 측정 결과 |
| `evidence/ocr_quality_hidpi_experiment.txt` | 2배 해상도 재측정 결과 |
| `evidence/ocr_hidpi_sample.txt` | 2배 해상도 캡처의 OCR 원문 |

---

측정 시각: 2026-08-05 (KST). 위 수치는 모두 해당 시점에 실제로 실행한 결과다.
