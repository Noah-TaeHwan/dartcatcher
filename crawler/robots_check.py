#!/usr/bin/env python3
"""robots.txt 확인 모듈 — 수집 전에 대상 URL이 허용되는지 검사한다.

README "크롤링 윤리" 절에서 사람이 한 번 읽고 판단하던 robots.txt 준수를
코드로 승격한 것이다. 파이프라인은 이 모듈로 각 대상 URL을 robots.txt 규칙과
대조하고, 하나라도 금지면 크롤링을 시작하기 전에 중단한다.

robots.txt 원문은 두 가지 경로에서 얻을 수 있다.

1. **로컬 파일 경로**(권장, 기본): 저장소 루트 기준 상대 경로.
   개발 중에는 사람이 이미 확인한 원문(`evidence/dart_robots.txt`)을 써서
   네트워크 요청 없이 동일한 판단을 재현한다.
2. **http(s) URL**: 사이트의 `/robots.txt` 실시간 주소. 표준
   `urllib.robotparser` 가 네트워크로 받아 파싱한다.

대량 요청 전에 이 모듈을 먼저 돌려 금지 경로가 섞여 있으면 실패로 끝낸다.
표준 라이브러리만 사용한다.
"""

from __future__ import annotations

import urllib.robotparser
from pathlib import Path
from typing import Iterable


def _parse(source: str, repo_root: Path) -> urllib.robotparser.RobotFileParser:
    """robots.txt 원문을 가져와 파서로 만든다.

    :param source: 저장소 루트 기준 로컬 파일 경로 또는 http(s) URL
    :param repo_root: 저장소 루트(상대 경로 해석의 기준)
    :returns: 파싱이 끝난 RobotFileParser
    :raises FileNotFoundError: 로컬 경로로 지정했는데 파일이 없는 경우
    :raises urllib.error.URLError: URL로 받으려는데 네트워크 요청이 실패한 경우
    """
    parser = urllib.robotparser.RobotFileParser()

    if source.startswith(("http://", "https://")):
        parser.set_url(source)
        parser.read()
        return parser

    path = (repo_root / source).resolve()
    parser.parse(path.read_text(encoding="utf-8").splitlines())
    return parser


def check_urls_allowed(
    source: str,
    user_agent: str,
    urls: Iterable[str],
    repo_root: Path,
) -> list[str]:
    """robots.txt 규칙으로 대상 URL들이 허용되는지 검사한다.

    :param source: robots.txt 원문의 로컬 파일 경로 또는 http(s) URL
    :param user_agent: can_fetch 판정에 쓸 사용자 에이전트 식별자
    :param urls: 금지 여부를 판단할 대상 URL 반복자
    :param repo_root: 저장소 루트(상대 경로 해석의 기준)
    :returns: robots.txt가 금지한 URL 목록. 비어 있으면 전부 허용됨
    """
    parser = _parse(source, repo_root)
    return [url for url in urls if not parser.can_fetch(user_agent, url)]
