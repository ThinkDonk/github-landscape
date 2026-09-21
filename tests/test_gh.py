"""Offline regression tests for sampled evidence and HTTP request accounting."""

import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "landscape_gh", Path(__file__).resolve().parents[1] / "scripts" / "gh.py"
)
gh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gh)


def repository():
    return {
        "full_name": "example/project",
        "html_url": "https://github.com/example/project",
        "stargazers_count": 12,
        "forks_count": 3,
        "open_issues_count": 21,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": "2025-01-01T00:00:00Z",
        "default_branch": "main",
    }


def response(value):
    result = mock.MagicMock()
    body = value if isinstance(value, str) else json.dumps(value)
    result.__enter__.return_value.read.return_value = body.encode("utf-8")
    return result


class LandscapeTests(unittest.TestCase):
    def setUp(self):
        gh.REQUEST_ATTEMPTS = 0
        # Any API access that a test forgot to mock must fail without networking.
        guard = mock.patch.object(
            gh.urllib.request, "urlopen", side_effect=AssertionError("network disabled")
        )
        guard.start()
        self.addCleanup(guard.stop)

    def inspect(self, issues=(), releases=(), contributors=(), readme="# Example"):
        args = argparse.Namespace(repo="example/project", max_issues=20, readme_chars=4000)
        values = [repository(), releases, [], contributors, readme, issues]
        stdout = io.StringIO()
        with mock.patch.object(gh, "api", side_effect=values), contextlib.redirect_stdout(stdout):
            gh.cmd_inspect(args)
        return stdout.getvalue()

    def test_pr_only_page_does_not_claim_repository_has_no_issues(self):
        output = self.inspect(issues=[{"number": 9, "pull_request": {}}])
        self.assertIn("1 条 issue/PR，其中 0 条 issue", output)
        self.assertIn("其他 open issue 未确认", output)
        self.assertNotIn("无 open issues", output)

    def test_empty_issue_page_is_reported_as_a_sample(self):
        output = self.inspect(issues=[])
        self.assertIn("API 返回 0 条", output)
        self.assertIn("当前页没有 issue 样本", output)
        self.assertNotIn("无 open issues", output)

    def test_unavailable_issue_endpoint_is_not_an_empty_result(self):
        output = self.inspect(issues=None)
        self.assertIn("端点不可访问，issue 情况未确认", output)
        self.assertNotIn("当前页没有 issue 样本", output)

    def test_mixed_issue_sample_preserves_source_and_excludes_pr(self):
        issue = {
            "number": 7,
            "title": "Export request",
            "html_url": "https://github.com/example/project/issues/7",
            "comments": 4,
        }
        output = self.inspect(issues=[{"number": 9, "pull_request": {}}, issue])
        self.assertIn("2 条 issue/PR，其中 1 条 issue", output)
        self.assertIn("[#7](https://github.com/example/project/issues/7)", output)
        self.assertNotIn("#9", output)
        self.assertIn("不能据此判断 issue 总数或问题出现频率", output)
        self.assertIn("open issues+PR 21", output)

    def test_release_sample_uses_publication_evidence_and_distinguishes_prerelease(self):
        releases = [
            {"tag_name": "draft-only", "draft": True, "prerelease": False,
             "published_at": "2026-06-01T00:00:00Z"},
            {"tag_name": "v1-stable", "draft": False, "prerelease": False,
             "published_at": "2025-01-01T00:00:00Z"},
            {"tag_name": "v2-beta", "draft": False, "prerelease": True,
             "published_at": "2026-01-01T00:00:00Z"},
            {"tag_name": "undated", "draft": False, "prerelease": False,
             "published_at": None},
            {"tag_name": "state-unknown", "published_at": "2026-07-01T00:00:00Z"},
        ]
        output = self.inspect(releases=releases)
        self.assertIn("API 返回 5 条；可确认已发布 2 条", output)
        self.assertIn("v1-stable (2025-01-01) [正式发布]", output)
        self.assertIn("v2-beta (2026-01-01) [预发布]", output)
        self.assertLess(output.index("v2-beta"), output.index("v1-stable"))
        for tag in ("draft-only", "undated", "state-unknown"):
            self.assertNotIn(tag, output)
        self.assertIn("不保证包含全仓库最新正式版", output)

    def test_unavailable_releases_are_not_reported_as_no_releases(self):
        output = self.inspect(releases=None)
        self.assertIn("端点不可访问，发布情况未确认", output)

    def test_full_contributor_page_does_not_invent_additional_contributors(self):
        contributors = [{"login": f"person-{i}", "contributions": 1} for i in range(10)]
        output = self.inspect(contributors=contributors)
        self.assertIn("是否还有更多未确认", output)
        self.assertNotIn("实际更多", output)

    def test_search_labels_github_combined_issue_pr_count(self):
        stdout = io.StringIO()
        data = {"total_count": 1, "items": [repository()]}
        with mock.patch.object(gh, "api", return_value=data), contextlib.redirect_stdout(stdout):
            gh.cmd_search(argparse.Namespace(query="example", top=30, sort="best"))
        self.assertIn("open issues+PR", stdout.getvalue())

    def test_missing_metadata_and_readme_do_not_imply_absence(self):
        for readme, expected in ((None, "README 未取得"), ("", "README 返回空内容")):
            with self.subTest(readme=readme):
                output = self.inspect(readme=readme)
                self.assertIn("license 未确认（需查许可文件）", output)
                self.assertIn(expected, output)
                self.assertNotIn("无 README", output)
                self.assertNotIn("license 无", output)

    def test_inspect_cli_keeps_six_requests_and_caps_single_mixed_page(self):
        values = [repository(), [], [], [], "# README", [{"number": 1, "pull_request": {}}]]
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(gh.urllib.request, "urlopen", side_effect=[response(v) for v in values]) as send:
            with mock.patch.object(gh.sys, "argv", ["gh.py", "inspect", "example/project", "--max-issues", "1000"]):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    gh.main()
        self.assertEqual(send.call_count, 6)
        issue_url = send.call_args_list[-1].args[0].full_url
        query = gh.urllib.parse.parse_qs(gh.urllib.parse.urlsplit(issue_url).query)
        self.assertEqual(query["per_page"], ["100"])
        self.assertNotIn("page", query)
        self.assertIn("HTTP 请求尝试：6 次", stderr.getvalue())

    def test_retry_is_included_in_actual_request_count(self):
        limited = gh.urllib.error.HTTPError(
            "https://api.github.com/search/repositories", 429, "limited",
            {"Retry-After": "0"}, io.BytesIO(),
        )
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(gh.urllib.request, "urlopen", side_effect=[limited, response({"items": [], "total_count": 0})]) as send:
            with mock.patch.object(gh.time, "sleep"), mock.patch.object(gh.sys, "argv", ["gh.py", "search", "example"]):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    gh.main()
        self.assertEqual(send.call_count, 2)
        self.assertIn("HTTP 请求尝试：2 次", stderr.getvalue())

    def test_failed_repository_lookup_still_reports_one_attempt(self):
        missing = gh.urllib.error.HTTPError(
            "https://api.github.com/repos/example/project", 404, "missing", {}, io.BytesIO()
        )
        stderr = io.StringIO()
        with mock.patch.object(gh.urllib.request, "urlopen", side_effect=missing):
            with mock.patch.object(gh.sys, "argv", ["gh.py", "inspect", "example/project"]):
                with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
                    gh.main()
        self.assertIn("不存在或不可访问", stderr.getvalue())
        self.assertIn("HTTP 请求尝试：1 次", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
