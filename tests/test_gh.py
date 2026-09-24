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


def issue_sample(number=7, state="closed"):
    return {"number": number, "title": "Resume interrupted download", "body": "断点续传尚未实现",
            "html_url": f"https://github.com/example/project/issues/{number}",
            "state": state, "state_reason": "not_planned" if state == "closed" else None,
            "comments": 3, "user": {"login": "reporter"}, "author_association": "NONE",
            "created_at": "2025-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
            "closed_at": "2026-01-01T00:00:00Z" if state == "closed" else None}


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

    def json_command(self, arguments, values, expected_exit=0):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(gh.urllib.request, "urlopen", side_effect=values) as fetch:
            with mock.patch.object(gh.sys, "argv", ["gh.py"] + arguments + ["--format", "json"]):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    if expected_exit:
                        with self.assertRaises(SystemExit) as error:
                            gh.main()
                        self.assertEqual(error.exception.code, expected_exit)
                    else:
                        gh.main()
        return json.loads(stdout.getvalue()), stderr.getvalue(), fetch

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

    def test_multi_query_deduplicates_by_id_and_preserves_all_sources(self):
        first = dict(repository(), id=1)
        renamed = dict(first, full_name="example/renamed")
        other = dict(repository(), id=2, full_name="example/other")
        values = [
            {"items": [first, other], "total_count": 50, "incomplete_results": False},
            {"items": [renamed], "total_count": 10, "incomplete_results": True},
        ]
        args = argparse.Namespace(query=["notes", "offline notes"], top=2, sort="best")
        with mock.patch.object(gh, "api", side_effect=values) as fetch:
            result = gh.collect_search(args)
        self.assertEqual(result["unique_count"], 2)
        self.assertEqual([r["full_name"] for r in result["repositories"]],
                         ["example/project", "example/other"])
        self.assertEqual(result["repositories"][0]["matched_queries"], ["Q1", "Q2"])
        self.assertEqual(result["repositories"][1]["matched_queries"], ["Q1"])
        self.assertEqual([q["total_count"] for q in result["queries"]], [50, 10])
        self.assertTrue(result["queries"][1]["incomplete_results"])
        self.assertEqual(fetch.call_args_list[1].args[1], {"q": "offline notes", "per_page": 2})
        self.assertIn("q=offline+notes", result["queries"][1]["source_url"])

    def test_repeated_queries_do_not_repeat_requests_or_attribution(self):
        args = argparse.Namespace(query=[" notes ", "notes"], top=1000, sort="stars")
        with mock.patch.object(gh, "api", return_value={"items": [repository()]}) as fetch:
            result = gh.collect_search(args)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(fetch.call_args.args[1]["per_page"], 100)
        self.assertEqual(result["repositories"][0]["matched_queries"], ["Q1"])

    def test_query_failure_keeps_other_results_and_returns_nonzero(self):
        invalid = gh.urllib.error.HTTPError("https://api.github.com/search/repositories",
                                           422, "invalid query", {}, io.BytesIO(b"invalid"))
        values = [response({"items": [repository()], "total_count": 1}), invalid,
                  response({"items": [], "total_count": 0})]
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(gh.urllib.request, "urlopen", side_effect=values) as fetch:
            with mock.patch.object(gh.sys, "argv", ["gh.py", "search", "notes", "bad", "offline"]):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    with self.assertRaises(SystemExit) as error:
                        gh.main()
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(fetch.call_count, 3)
        self.assertIn("example/project", stdout.getvalue())
        self.assertIn("Q2: error", stdout.getvalue())
        self.assertIn("Q3: 共 0 个结果", stdout.getvalue())
        self.assertIn("HTTP 请求尝试：3 次", stderr.getvalue())

    def test_connection_failure_stops_remaining_queries_with_explicit_status(self):
        args = argparse.Namespace(query=["first", "second", "third"], top=30, sort="best")
        with mock.patch.object(gh.urllib.request, "urlopen", side_effect=[
            response({"items": [repository()]}), gh.urllib.error.URLError("offline")
        ]) as fetch:
            result = gh.collect_search(args)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(result["status"], "partial")
        self.assertEqual([q["status"] for q in result["queries"]], ["ok", "error", "skipped"])
        self.assertEqual(result["unique_count"], 1)

    def test_all_failed_queries_are_not_successful_empty_searches(self):
        args = argparse.Namespace(query=["first", "second"], top=30, sort="best")
        with mock.patch.object(gh, "api", return_value=None):
            result = gh.collect_search(args)
        self.assertEqual(result["status"], "error")
        self.assertTrue(all(q["status"] == "error" for q in result["queries"]))
        self.assertTrue(all("total_count" not in q for q in result["queries"]))

    def test_invalid_search_limits_and_blank_queries_do_not_call_api(self):
        for arguments in (["search", "notes", "--top", "0"], ["search", " "]):
            with self.subTest(arguments=arguments), mock.patch.object(gh, "api") as fetch:
                with mock.patch.object(gh.sys, "argv", ["gh.py"] + arguments):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        gh.main()
            fetch.assert_not_called()

    def test_json_search_is_parseable_preserves_unicode_and_query_provenance(self):
        gh.REQUEST_ATTEMPTS = 40  # Output accounting must be scoped to this command.
        item = dict(repository(), id=1, description="离线 | 笔记\n同步")
        document, stderr, _ = self.json_command(["search", "笔记", "offline", "--top", "1"], [
            response({"items": [item], "total_count": 20, "incomplete_results": False}),
            response({"items": [item], "total_count": 1, "incomplete_results": True}),
        ])
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["command"], "search")
        self.assertEqual(document["status"], "ok")
        self.assertEqual(document["request_attempts"], 2)
        self.assertTrue(document["collected_at"].endswith("Z"))
        self.assertEqual(document["repositories"][0]["description"], "离线 | 笔记\n同步")
        self.assertEqual(document["repositories"][0]["matched_queries"], ["Q1", "Q2"])
        self.assertTrue(document["queries"][0]["truncated"])
        self.assertFalse(document["queries"][1]["truncated"])
        self.assertTrue(document["queries"][1]["incomplete_results"])
        self.assertIn("HTTP 请求尝试：2 次", stderr)

    def test_json_search_failure_remains_parseable_and_preserves_success(self):
        document, _, fetch = self.json_command(["search", "notes", "offline", "sync"], [
            response({"items": [repository()], "total_count": 1}),
            gh.urllib.error.URLError("offline"),
        ], expected_exit=1)
        self.assertEqual(document["status"], "partial")
        self.assertEqual(document["request_attempts"], 2)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(document["unique_count"], 1)
        self.assertEqual(document["queries"][2]["status"], "skipped")
        self.assertIsNone(document["queries"][2]["collected_at"])

    def test_json_inspect_preserves_sample_bounds_sources_and_unknown_data(self):
        missing = gh.urllib.error.HTTPError("https://api.github.com/example", 404, "missing", {}, io.BytesIO())
        releases = [{"tag_name": "draft", "draft": True, "published_at": None}]
        issue = {"number": 7, "title": "Sync", "html_url": "https://github.com/example/project/issues/7"}
        document, _, _ = self.json_command(["inspect", "example/project", "--readme-chars", "2"], [
            response(repository()), response(releases), response([]), missing,
            response("笔记同步"), response([{"number": 8, "pull_request": {}}, issue]),
        ], expected_exit=1)
        self.assertEqual(document["status"], "partial")
        self.assertEqual(document["request_attempts"], 6)
        self.assertEqual(document["commits"]["data"], [])
        self.assertEqual(document["commits"]["status"], "ok")
        self.assertIsNone(document["contributors"]["data"])
        self.assertEqual(document["contributors"]["status"], "unavailable")
        self.assertEqual(document["releases"]["data"], releases)
        self.assertEqual(document["readme"]["data"], "笔记")
        self.assertTrue(document["readme"]["truncated"])
        self.assertEqual(document["readme"]["original_characters"], 4)
        self.assertEqual(document["issues"]["data"], [issue])
        self.assertEqual(document["issues"]["returned_count"], 2)
        self.assertEqual(document["issues"]["pull_requests_excluded"], 1)
        self.assertFalse(document["issues"]["paginated"])
        self.assertEqual(document["issues"]["sample_limit"], 20)
        self.assertIn("state=open", document["issues"]["source_url"])

    def test_json_inspect_connection_failure_preserves_earlier_evidence(self):
        document, _, fetch = self.json_command(["inspect", "example/project"], [
            response(repository()), response([]), gh.urllib.error.URLError("offline"),
        ], expected_exit=1)
        self.assertEqual(document["request_attempts"], 3)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(document["repository"]["data"]["full_name"], "example/project")
        self.assertEqual(document["releases"]["data"], [])
        self.assertEqual(document["commits"]["status"], "error")
        self.assertEqual(document["readme"]["status"], "skipped")
        self.assertIsNone(document["readme"]["truncated"])
        self.assertIsNone(document["issues"]["returned_count"])

    def test_json_missing_repository_emits_one_error_document(self):
        missing = gh.urllib.error.HTTPError("https://api.github.com/example", 404, "missing", {}, io.BytesIO())
        document, _, _ = self.json_command(["inspect", "example/project"], [missing], expected_exit=1)
        self.assertEqual(document["status"], "error")
        self.assertEqual(document["request_attempts"], 1)
        self.assertIsNone(document["repository"]["data"])
        self.assertEqual(document["repository"]["status"], "unavailable")

    def test_json_rate_preserves_resources_and_request_count(self):
        value = {"resources": {"core": {"limit": 60, "remaining": 30, "reset": 1800000000}}}
        document, _, _ = self.json_command(["rate"], [response(value)])
        self.assertEqual(document["command"], "rate")
        self.assertEqual(document["rate_limit"]["data"], value)
        self.assertEqual(document["request_attempts"], 1)

    def test_feature_issue_search_scopes_repository_includes_closed_and_excludes_prs(self):
        document, _, fetch = self.json_command(["issues", "example/project", "断点续传", "--body-chars", "4"], [
            response({"total_count": 10, "incomplete_results": True,
                      "items": [issue_sample(), issue_sample(8, "open"), {"number": 9, "pull_request": {}}]})
        ])
        url = fetch.call_args.args[0].full_url
        params = gh.urllib.parse.parse_qs(gh.urllib.parse.urlsplit(url).query)
        self.assertEqual(params["q"], ["断点续传 repo:example/project is:issue in:title,body,comments"])
        self.assertNotIn("sort", params)
        self.assertEqual(document["request_attempts"], 1)
        self.assertEqual(document["state"], "all")
        section = document["issues"]
        self.assertEqual([i["state"] for i in section["data"]], ["closed", "open"])
        self.assertEqual(section["data"][0]["state_reason"], "not_planned")
        self.assertEqual(section["data"][0]["body"], "断点续传")
        self.assertTrue(section["data"][0]["body_truncated"])
        self.assertEqual(section["data"][0]["html_url"], issue_sample()["html_url"])
        self.assertEqual(section["data"][0]["updated_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(section["pull_requests_excluded"], 1)
        self.assertTrue(section["truncated"])
        self.assertTrue(section["incomplete_results"])

    def test_feature_issue_state_sort_and_page_limit_are_sent_to_github(self):
        document, _, fetch = self.json_command([
            "issues", "example/project", '"offline sync"', "--state", "closed", "--sort", "updated", "--top", "1000"
        ], [response({"items": [], "total_count": 0, "incomplete_results": False})])
        params = gh.urllib.parse.parse_qs(gh.urllib.parse.urlsplit(fetch.call_args.args[0].full_url).query)
        self.assertEqual(params["q"], ['"offline sync" repo:example/project is:issue in:title,body,comments state:closed'])
        self.assertEqual(params["sort"], ["updated"])
        self.assertEqual(params["per_page"], ["100"])
        self.assertNotIn("page", params)
        self.assertEqual(document["issues"]["data"], [])
        self.assertEqual(document["status"], "ok")

    def test_issue_input_cannot_override_repository_type_state_or_fields(self):
        queries = [" ", "resume repo:other/project", "resume is:pr", "resume state:open",
                   "resume in:title", "resume OR unrelated", "resume user:someone"]
        arguments = [["issues", "example/project", query] for query in queries]
        arguments += [["issues", "example/project?x=1", "sync"], ["issue", "example/project", "0"],
                      ["issue", "example/project", "7", "--max-comments", "0"]]
        for command in arguments:
            with self.subTest(command=command), mock.patch.object(gh, "api") as fetch:
                with mock.patch.object(gh.sys, "argv", ["gh.py"] + command):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        gh.main()
                fetch.assert_not_called()

    def test_failed_issue_search_does_not_become_an_empty_match(self):
        document, _, _ = self.json_command(["issues", "example/project", "sync"], [
            gh.urllib.error.URLError("offline")
        ], expected_exit=1)
        self.assertEqual(document["status"], "error")
        self.assertIsNone(document["issues"]["data"])
        self.assertNotIn("total_count", document["issues"])

    def test_issue_detail_preserves_comment_sources_and_marks_sampling(self):
        comment = {"id": 11, "html_url": "https://github.com/example/project/issues/7#issuecomment-11",
                   "body": "请参考后续讨论", "user": {"login": "maintainer"}, "author_association": "MEMBER",
                   "created_at": "2025-02-01T00:00:00Z", "updated_at": "2025-02-02T00:00:00Z"}
        document, _, fetch = self.json_command([
            "issue", "example/project", "7", "--max-comments", "1", "--body-chars", "3"
        ], [response(issue_sample()), response([comment])])
        self.assertEqual(document["request_attempts"], 2)
        self.assertEqual(document["issue"]["data"]["state_reason"], "not_planned")
        self.assertEqual(document["issue"]["data"]["body"], "断点续")
        self.assertTrue(document["issue"]["data"]["body_truncated"])
        comments = document["comments"]
        self.assertEqual(comments["order"], "id_asc")
        self.assertEqual(comments["reported_total"], 3)
        self.assertTrue(comments["truncated"])
        self.assertFalse(comments["paginated"])
        self.assertEqual(comments["data"][0]["html_url"], comment["html_url"])
        self.assertEqual(comments["data"][0]["user"]["login"], "maintainer")
        self.assertEqual(comments["data"][0]["body"], "请参考")
        self.assertEqual(comments["data"][0]["created_at"], comment["created_at"])
        self.assertTrue(fetch.call_args.args[0].full_url.endswith("/issues/7/comments?per_page=1"))

    def test_issue_detail_comment_failure_keeps_issue_evidence(self):
        document, _, _ = self.json_command(["issue", "example/project", "7"], [
            response(issue_sample()), gh.urllib.error.URLError("offline")
        ], expected_exit=1)
        self.assertEqual(document["status"], "partial")
        self.assertEqual(document["issue"]["data"]["body"], issue_sample()["body"])
        self.assertEqual(document["comments"]["status"], "error")
        self.assertIsNone(document["comments"]["data"])
        self.assertNotIn("returned_count", document["comments"])

    def test_issue_detail_rejects_pull_request_without_fetching_comments(self):
        document, _, fetch = self.json_command(["issue", "example/project", "9"], [
            response(dict(issue_sample(9), pull_request={"url": "https://api.github.com/example"}))
        ], expected_exit=1)
        self.assertEqual(document["status"], "error")
        self.assertEqual(fetch.call_count, 1)
        self.assertNotIn("comments", document)
        self.assertIn("pull request", document["issue"]["error"])

    def test_issue_detail_missing_issue_does_not_fetch_comments(self):
        missing = gh.urllib.error.HTTPError("https://api.github.com/example", 404, "missing", {}, io.BytesIO())
        document, _, fetch = self.json_command(["issue", "example/project", "7"], [missing], expected_exit=1)
        self.assertEqual(document["issue"]["status"], "unavailable")
        self.assertEqual(fetch.call_count, 1)
        self.assertNotIn("comments", document)

    def test_issue_markdown_retains_closed_context_and_comment_caveat(self):
        comment = {"id": 11, "html_url": "https://github.com/example/project/issues/7#issuecomment-11",
                   "body": "No release planned.", "user": {"login": "maintainer"}}
        stdout = io.StringIO()
        args = argparse.Namespace(repo="example/project", number=7, max_comments=20, body_chars=4000)
        with mock.patch.object(gh, "api", side_effect=[issue_sample(), [comment]]):
            with contextlib.redirect_stdout(stdout):
                gh.cmd_issue(args)
        output = stdout.getvalue()
        self.assertIn("not_planned", output)
        self.assertIn("断点续传尚未实现", output)
        self.assertIn(comment["html_url"], output)
        self.assertIn("No release planned.", output)
        self.assertIn("不单独证明已修复", output)
        self.assertIn("可能未包含最终结论", output)

    def test_issue_empty_and_missing_bodies_are_distinct(self):
        document, _, fetch = self.json_command(["issue", "example/project", "7", "--max-comments", "1000"], [
            response(dict(issue_sample(), body=None, comments=1)),
            response([{"id": 1, "html_url": "https://example.test/comment/1", "body": ""}]),
        ])
        self.assertIsNone(document["issue"]["data"]["body"])
        self.assertIsNone(document["issue"]["data"]["body_truncated"])
        self.assertEqual(document["comments"]["data"][0]["body"], "")
        self.assertFalse(document["comments"]["data"][0]["body_truncated"])
        self.assertFalse(document["comments"]["truncated"])
        self.assertTrue(fetch.call_args.args[0].full_url.endswith("per_page=100"))

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
