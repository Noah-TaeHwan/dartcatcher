#!/usr/bin/env python3
"""robots.txt 자동 확인과 대상 URL 설정 분리에 대한 테스트.

실행:
    python3 -m unittest discover -s crawler
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import crawl_dart  # noqa: E402
from robots_check import check_urls_allowed  # noqa: E402

CONFIG = crawl_dart.DEFAULT_CONFIG
REPO_ROOT = crawl_dart.REPO_ROOT


class RobotsCheckTest(unittest.TestCase):
    """robots.txt 허용·거부 판정이 evidence 원문과 일치하는지 확인한다."""

    def setUp(self) -> None:
        self.site = crawl_dart.load_site(CONFIG, "dart")

    def test_config_has_expected_fields(self) -> None:
        for key in (
            "user_agent",
            "robots_source",
            "list_url_template",
            "request_interval_sec",
            "pages",
        ):
            self.assertIn(key, self.site)

    def test_target_urls_all_allowed(self) -> None:
        urls = crawl_dart.build_page_urls(
            self.site["list_url_template"], self.site["pages"]
        )
        self.assertEqual(len(urls), len(self.site["pages"]))
        denied = check_urls_allowed(
            self.site["robots_source"],
            self.site["user_agent"],
            urls,
            REPO_ROOT,
        )
        self.assertEqual(denied, [])

    def test_disallowed_viewer_path_is_denied(self) -> None:
        denied = check_urls_allowed(
            self.site["robots_source"],
            self.site["user_agent"],
            ["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=1"],
            REPO_ROOT,
        )
        self.assertEqual(len(denied), 1)

    def test_other_undisallowed_path_is_allowed(self) -> None:
        denied = check_urls_allowed(
            self.site["robots_source"],
            self.site["user_agent"],
            ["https://dart.fss.or.kr/somewhere/else"],
            REPO_ROOT,
        )
        self.assertEqual(denied, [])


class SiteConfigSeparationTest(unittest.TestCase):
    """대상 URL이 설정 파일에서 읽히고 다른 사이트에도 적용 가능한지 확인한다."""

    def test_verify_robots_aborts_on_denied_url(self) -> None:
        site = crawl_dart.load_site(CONFIG, "dart")
        urls = ["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=1"]
        with self.assertRaises(SystemExit):
            crawl_dart.verify_robots(site, urls)

    def test_verify_robots_passes_on_allowed_urls(self) -> None:
        site = crawl_dart.load_site(CONFIG, "dart")
        urls = crawl_dart.build_page_urls(
            site["list_url_template"], site["pages"]
        )
        crawl_dart.verify_robots(site, urls)  # SystemExit 없으면 통과

    def test_default_site_is_dart(self) -> None:
        site = crawl_dart.load_site(CONFIG, "dart")
        self.assertEqual(site["request_interval_sec"], 2.5)
        self.assertEqual(site["pages"], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
