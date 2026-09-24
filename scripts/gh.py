#!/usr/bin/env python3
"""gh.py — github-landscape skill 的数据层：搜索 GitHub 仓库并拉取维护度指标。

零依赖（仅 Python 标准库），匿名可用；设置 GITHUB_TOKEN 环境变量可提升限额。

用法:
  gh.py search "<query>" ["<query>" ...] [--top 30] [--sort stars|best|forks|updated]
  gh.py inspect <owner/repo> [--max-issues 20] [--readme-chars 4000]
  gh.py rate

search / inspect / rate 均支持 --format markdown|json（默认 markdown）。
"""

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
REQUEST_ATTEMPTS = 0


class ApiError(Exception):
    def __init__(self, message, stop=False):
        super().__init__(message)
        self.stop = stop


def die(msg):
    print(f"错误: {msg}", file=sys.stderr)
    sys.exit(1)


def api(path, params=None, raw=False):
    """GET 一个 API 资源；404 返回 None；限速时按响应头自动等待重试。"""
    global REQUEST_ATTEMPTS
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
               "User-Agent": "github-landscape"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    for _ in range(5):
        req = urllib.request.Request(url, headers=headers)
        try:
            REQUEST_ATTEMPTS += 1
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
                return body if raw else json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            remaining = e.headers.get("X-RateLimit-Remaining")
            retry_after = e.headers.get("Retry-After")
            if e.code == 429 or remaining == "0" or retry_after:
                if retry_after:
                    wait = min(int(retry_after) + 1, 120)
                elif remaining == "0":
                    reset = e.headers.get("X-RateLimit-Reset")
                    wait = max(int(reset) - int(time.time()) + 1, 2) if reset else 30
                    if wait > 600:
                        at = dt.datetime.fromtimestamp(int(reset)).astimezone().strftime("%H:%M:%S")
                        raise ApiError(f"API 限额耗尽，{at} 重置（约 {wait // 60} 分钟）；届时重跑，或设置 GITHUB_TOKEN 提升限额", stop=True)
                else:
                    wait = 30
                print(f"限速，等待 {wait}s 后重试…", file=sys.stderr)
                time.sleep(wait)
                continue
            raise ApiError(f"HTTP {e.code} {url}\n{e.read().decode('utf-8', 'replace')[:300]}",
                           stop=e.code in (401, 403)) from e
        except urllib.error.URLError as e:
            raise ApiError(f"网络错误 {url}: {e.reason}", stop=True) from e
        except (TimeoutError, json.JSONDecodeError) as e:
            raise ApiError(f"响应未取得或无法解析 {url}: {e}", stop=True) from e
    raise ApiError(f"重试次数用尽: {url}", stop=True)


def days_since(iso):
    if not iso:
        return None
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (dt.datetime.now(dt.timezone.utc) - d).days


def cell(v):
    return str(v if v is not None else "?")


def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def source_url(path, params=None):
    return API + path + ("?" + urllib.parse.urlencode(params) if params else "")


class EvidenceCollector:
    """保留每个端点的取证状态，系统性故障后不再发起请求。"""

    def __init__(self):
        self.stopped = None

    def fetch(self, path, params=None, raw=False):
        record = {"source_url": source_url(path, params), "collected_at": None, "data": None}
        if self.stopped:
            return dict(record, status="skipped", error=self.stopped)
        record["collected_at"] = timestamp()
        try:
            data = api(path, params, raw=raw)
        except ApiError as e:
            if e.stop:
                self.stopped = "前一请求遇到连接、认证或限额问题，停止后续请求"
            return dict(record, status="error", error=str(e))
        if data is None:
            return dict(record, status="unavailable", error="端点不存在或不可访问；内容未确认")
        return dict(record, status="ok", data=data)


def emit_result(command, args, result, renderer, before):
    if getattr(args, "format", "markdown") == "json":
        document = {"schema_version": 1, "command": command, "collected_at": timestamp(),
                    "request_attempts": REQUEST_ATTEMPTS - before, **result}
        print(json.dumps(document, ensure_ascii=False, indent=2))
    else:
        renderer(result)
    return 0 if result["status"] == "ok" else 1


def collect_search(args):
    queries = [args.query] if isinstance(args.query, str) else args.query
    queries = list(dict.fromkeys(q.strip() for q in queries))
    if not all(queries):
        die("查询不能为空")
    records, repositories = [], {}
    stopped = None
    for index, query in enumerate(queries, 1):
        params = {"q": query, "per_page": min(args.top, 100)}
        if args.sort != "best":
            params.update(sort=args.sort, order="desc")
        record = {"id": f"Q{index}", "query": query, "collected_at": None,
                  "source_url": source_url("/search/repositories", params)}
        records.append(record)
        if stopped:
            record.update(status="skipped", error=stopped)
            continue
        record["collected_at"] = timestamp()
        try:
            data = api("/search/repositories", params)
            if data is None:
                raise ApiError("搜索端点不存在或不可访问")
        except ApiError as e:
            record.update(status="error", error=str(e))
            if e.stop:
                stopped = "前一查询遇到连接、认证或限额问题，停止后续请求"
            continue
        items = data.get("items", [])
        record.update(status="ok", total_count=data.get("total_count"),
                      returned_count=len(items), incomplete_results=data.get("incomplete_results"),
                      sample_limit=params["per_page"], paginated=False,
                      truncated=data["total_count"] > len(items) if isinstance(data.get("total_count"), int) else None)
        for item in items:
            key = ("id", item["id"]) if item.get("id") is not None else ("name", item["full_name"].lower())
            if key not in repositories:
                repositories[key] = dict(item, matched_queries=[])
            matches = repositories[key]["matched_queries"]
            if record["id"] not in matches:
                matches.append(record["id"])
    successes = sum(r["status"] == "ok" for r in records)
    return {"status": "ok" if successes == len(records) else "partial" if successes else "error",
            "queries": records, "repositories": list(repositories.values()),
            "unique_count": len(repositories), "sort": args.sort, "per_query_limit": min(args.top, 100)}


def render_search(result):
    for query in result["queries"]:
        if query["status"] == "ok":
            print(f"{query['id']}: 共 {query.get('total_count')} 个结果，取前 {query['returned_count']}（query: {query['query']}，sort: {result['sort']}）")
            if query.get("incomplete_results"):
                print("GitHub 标记本次搜索结果不完整。")
        else:
            print(f"{query['id']}: {query['status']}（query: {query['query']}）：{query['error']}")
    items = result["repositories"]
    print(f"\n合并去重后 {len(items)} 个仓库；每条查询仅取一页，按首次出现顺序展示。")
    print("命中查询表示来源，不是功能适配评分；各查询总数不能相加作为唯一仓库总数。\n")
    if not items:
        return
    print("| 仓库 | stars | forks | open issues+PR | push天数 | 存档 | license | 简介 | 命中查询 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for it in items:
        desc = (it.get("description") or "").replace("|", "/").replace("\n", " ")[:80]
        lic = (it.get("license") or {}).get("spdx_id") or "-"
        arch = "已存档" if it.get("archived") else ""
        print(f"| [{it['full_name']}]({it['html_url']}) | {it['stargazers_count']} | "
              f"{it['forks_count']} | {it['open_issues_count']} | {cell(days_since(it.get('pushed_at')))} | "
              f"{arch} | {lic} | {desc} | {', '.join(it['matched_queries'])} |")


def cmd_search(args):
    before = REQUEST_ATTEMPTS
    result = collect_search(args)
    return emit_result("search", args, result, render_search, before)


def collect_inspect(args):
    if args.repo.count("/") != 1:
        die("仓库格式应为 owner/repo")
    base = f"/repos/{args.repo}"
    collector = EvidenceCollector()
    result = {"repo": args.repo, "repository": collector.fetch(base)}
    if result["repository"]["status"] != "ok":
        return dict(result, status="error")
    endpoints = [("releases", {"per_page": 5}), ("commits", {"per_page": 15}),
                 ("contributors", {"per_page": 10}), ("readme", None),
                 ("issues", {"state": "open", "per_page": min(args.max_issues, 100),
                             "sort": "updated", "direction": "desc"})]
    for name, params in endpoints:
        record = collector.fetch(f"{base}/{name}", params, raw=name == "readme")
        result[name] = record
        if name == "readme":
            data = record["data"]
            record.update(character_limit=args.readme_chars,
                          original_characters=len(data) if data is not None else None,
                          truncated=len(data) > args.readme_chars if data is not None else None)
            if data is not None:
                record["data"] = data[:args.readme_chars]
        else:
            data = record["data"]
            record.update(sample_limit=params["per_page"], paginated=False,
                          returned_count=len(data) if data is not None else None,
                          limit_reached=len(data) == params["per_page"] if data is not None else None)
            if name == "issues":
                record["data"] = [i for i in data if "pull_request" not in i] if data is not None else None
                record["issue_count"] = len(record["data"]) if data is not None else None
                record["pull_requests_excluded"] = len(data) - record["issue_count"] if data is not None else None
    result["status"] = "ok" if all(result[name]["status"] == "ok" for name, _ in endpoints) else "partial"
    return result


def render_inspect(result):
    if result["repository"]["status"] != "ok":
        print(f"错误: 仓库 {result['repo']}：{result['repository']['error']}", file=sys.stderr)
        return
    repo = result["repository"]["data"]
    print(f"# {repo['full_name']}")
    print(f"{repo.get('description') or ''}\n")
    pushed = repo.get("pushed_at")
    lic = (repo.get("license") or {}).get("spdx_id") or "未确认（需查许可文件）"
    print(f"stars {repo['stargazers_count']} | forks {repo['forks_count']} | "
          f"open issues+PR {repo['open_issues_count']} | 创建 {repo.get('created_at', '')[:10]} | "
          f"最后 push {pushed[:10] if pushed else '?'}（{cell(days_since(pushed))} 天前）")
    print(f"license {lic} | archived {'是' if repo.get('archived') else '否'} | "
          f"默认分支 {repo.get('default_branch')} | topics: {', '.join(repo.get('topics') or []) or '-'}\n")

    rel = result["releases"]["data"]
    if rel is None:
        print("## releases：端点不可访问，发布情况未确认")
        print(result["releases"]["error"])
    else:
        published = [x for x in rel if x.get("draft") is False and x.get("published_at")]
        published.sort(key=lambda x: x["published_at"], reverse=True)
        print(f"## releases（API 返回 {len(rel)} 条；可确认已发布 {len(published)} 条，按发布时间排序）")
        print("仅当前页样本，未翻页；不保证包含全仓库最新正式版。")
        if len(published) != len(rel):
            print(f"另有 {len(rel) - len(published)} 条草稿或发布状态/时间未确认，未计入已发布样本。")
        for x in published:
            kind = {True: "预发布", False: "正式发布"}.get(x.get("prerelease"), "发布类型未确认")
            print(f"- {x.get('tag_name')} ({x['published_at'][:10]}) [{kind}] {(x.get('name') or '')}")
    print()

    commits = result["commits"]["data"]
    if commits:
        dates = [(c.get("commit", {}).get("author", {}).get("date") or "")[:10] for c in commits]
        print(f"## commits（最近 {len(commits)} 条，{dates[-1]} ~ {dates[0]}）")
        for c in commits:
            msg = (c.get("commit", {}).get("message") or "").split("\n", 1)[0][:70]
            d = (c.get("commit", {}).get("author", {}).get("date") or "")[:10]
            print(f"- {d} {msg}")
    elif commits is None:
        print(f"## commits：未取得，提交情况未确认；{result['commits']['error']}")
    else:
        print("## commits：当前页为空")
    print()

    contribs = result["contributors"]["data"]
    if contribs:
        names = ", ".join(f"{c.get('login')}({c.get('contributions')})" for c in contribs)
        mark = "（当前页 10 条，是否还有更多未确认）" if len(contribs) == 10 else ""
        print(f"## contributors{mark}: {names}\n")
    elif contribs is None:
        print(f"## contributors：未取得，贡献者情况未确认；{result['contributors']['error']}\n")
    else:
        print("## contributors：当前页为空\n")

    readme = result["readme"]["data"]
    print(f"## README（前 {result['readme']['character_limit']} 字符）")
    if readme is None:
        print("README 未取得，端点不存在或不可访问；内容未确认")
        print(result["readme"]["error"])
    elif readme:
        print(readme)
        if result["readme"]["truncated"]:
            print("\n…（已截断）")
    else:
        print("README 返回空内容")
    print()

    issues = result["issues"]["data"]
    if issues is None:
        print("## open issues：端点不可访问，issue 情况未确认")
        print(result["issues"]["error"])
        return
    print(f"## open issues（更新倒序样本：API 返回 {result['issues']['returned_count']} 条 issue/PR，其中 {len(issues)} 条 issue）")
    print("仅当前页，未翻页；不能据此判断 issue 总数或问题出现频率。")
    if not issues:
        print("当前页没有 issue 样本，仓库是否存在其他 open issue 未确认。")
    for i in issues:
        labels = ",".join(l["name"] for l in i.get("labels", []))
        labels = f"[{labels}]" if labels else ""
        source = f"[#{i['number']}]({i['html_url']})" if i.get("html_url") else f"#{i['number']}"
        print(f"- {source} {i['title'][:70]} {labels} 评论{ i.get('comments', 0)} 更新{i.get('updated_at', '')[:10]}")


def cmd_inspect(args):
    before = REQUEST_ATTEMPTS
    result = collect_inspect(args)
    return emit_result("inspect", args, result, render_inspect, before)


def render_rate(result):
    if result["rate_limit"]["status"] != "ok":
        print(f"错误: {result['rate_limit']['error']}", file=sys.stderr)
        return
    d = result["rate_limit"]["data"]
    for k in ("core", "search"):
        rr = d["resources"][k]
        reset = dt.datetime.fromtimestamp(rr["reset"], dt.timezone.utc).astimezone().strftime("%H:%M:%S")
        print(f"{k}: 剩余 {rr['remaining']}/{rr['limit']}，{reset} 重置")


def cmd_rate(args):
    before = REQUEST_ATTEMPTS
    record = EvidenceCollector().fetch("/rate_limit")
    result = {"status": "ok" if record["status"] == "ok" else "error", "rate_limit": record}
    return emit_result("rate", args, result, render_rate, before)


def main():
    for stream in (sys.stdout, sys.stderr):
        if stream.encoding and stream.encoding.lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__,
                               formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("search", help="搜索仓库，输出候选池表格")
    ps.add_argument("query", nargs="+", help="一条或多条独立查询；每条用引号包裹")
    ps.add_argument("--top", type=positive_int, default=30, help="每条查询取前多少条，最多 100（默认 30）")
    ps.add_argument("--sort", choices=["stars", "best", "forks", "updated"], default="stars")
    pi = sub.add_parser("inspect", help="拉取单个仓库的维护证据样本（6 次请求，不翻页）")
    pi.add_argument("repo", help="owner/repo")
    pi.add_argument("--max-issues", type=positive_int, default=20, help="单页 issue/PR 混合样本条数，最多 100（默认 20）")
    pi.add_argument("--readme-chars", type=positive_int, default=4000)
    pr = sub.add_parser("rate", help="查看 API 限额")
    for parser in (ps, pi, pr):
        parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="输出格式（默认 markdown）")
    args = p.parse_args()
    before = REQUEST_ATTEMPTS
    try:
        status = {"search": cmd_search, "inspect": cmd_inspect, "rate": cmd_rate}[args.cmd](args)
        if status:
            sys.exit(status)
    except ApiError as e:
        die(str(e))
    finally:
        print(f"HTTP 请求尝试：{REQUEST_ATTEMPTS - before} 次（含失败和限速重试）", file=sys.stderr)


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("必须为正整数")
    return number


if __name__ == "__main__":
    main()
