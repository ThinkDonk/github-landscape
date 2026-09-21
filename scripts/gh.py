#!/usr/bin/env python3
"""gh.py — github-landscape skill 的数据层：搜索 GitHub 仓库并拉取维护度指标。

零依赖（仅 Python 标准库），匿名可用；设置 GITHUB_TOKEN 环境变量可提升限额。

用法:
  gh.py search "<query>" [--top 30] [--sort stars|best|forks|updated]
  gh.py inspect <owner/repo> [--max-issues 20] [--readme-chars 4000]
  gh.py rate
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
                        die(f"API 限额耗尽，{at} 重置（约 {wait // 60} 分钟）；届时重跑，或设置 GITHUB_TOKEN 提升限额")
                else:
                    wait = 30
                print(f"限速，等待 {wait}s 后重试…", file=sys.stderr)
                time.sleep(wait)
                continue
            die(f"HTTP {e.code} {url}\n{e.read().decode('utf-8', 'replace')[:300]}")
        except urllib.error.URLError as e:
            die(f"网络错误 {url}: {e.reason}")
    die(f"重试次数用尽: {url}")


def days_since(iso):
    if not iso:
        return None
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (dt.datetime.now(dt.timezone.utc) - d).days


def cell(v):
    return str(v if v is not None else "?")


def cmd_search(args):
    params = {"q": args.query, "per_page": min(args.top, 100)}
    if args.sort != "best":
        params["sort"] = args.sort
        params["order"] = "desc" if args.sort != "updated" else "desc"
    data = api("/search/repositories", params)
    items = data.get("items", [])
    print(f"共 {data.get('total_count')} 个结果，取前 {len(items)}（query: {args.query}，sort: {args.sort}）\n")
    if not items:
        return
    print("| 仓库 | stars | forks | open issues+PR | push天数 | 存档 | license | 简介 |")
    print("|---|---|---|---|---|---|---|---|")
    for it in items:
        desc = (it.get("description") or "").replace("|", "/").replace("\n", " ")[:80]
        lic = (it.get("license") or {}).get("spdx_id") or "-"
        arch = "已存档" if it.get("archived") else ""
        print(f"| [{it['full_name']}]({it['html_url']}) | {it['stargazers_count']} | "
              f"{it['forks_count']} | {it['open_issues_count']} | {cell(days_since(it.get('pushed_at')))} | "
              f"{arch} | {lic} | {desc} |")


def cmd_inspect(args):
    if args.repo.count("/") != 1:
        die("仓库格式应为 owner/repo")
    o, r = args.repo.split("/")
    repo = api(f"/repos/{o}/{r}")
    if repo is None:
        die(f"仓库 {args.repo} 不存在或不可访问")
    print(f"# {repo['full_name']}")
    print(f"{repo.get('description') or ''}\n")
    pushed = repo.get("pushed_at")
    lic = (repo.get("license") or {}).get("spdx_id") or "未确认（需查许可文件）"
    print(f"stars {repo['stargazers_count']} | forks {repo['forks_count']} | "
          f"open issues+PR {repo['open_issues_count']} | 创建 {repo.get('created_at', '')[:10]} | "
          f"最后 push {pushed[:10] if pushed else '?'}（{cell(days_since(pushed))} 天前）")
    print(f"license {lic} | archived {'是' if repo.get('archived') else '否'} | "
          f"默认分支 {repo.get('default_branch')} | topics: {', '.join(repo.get('topics') or []) or '-'}\n")

    rel = api(f"/repos/{o}/{r}/releases", {"per_page": 5})
    if rel is None:
        print("## releases：端点不可访问，发布情况未确认")
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

    commits = api(f"/repos/{o}/{r}/commits", {"per_page": 15})
    if commits:
        dates = [(c.get("commit", {}).get("author", {}).get("date") or "")[:10] for c in commits]
        print(f"## commits（最近 {len(commits)} 条，{dates[-1]} ~ {dates[0]}）")
        for c in commits:
            msg = (c.get("commit", {}).get("message") or "").splitlines()[0][:70]
            d = (c.get("commit", {}).get("author", {}).get("date") or "")[:10]
            print(f"- {d} {msg}")
    else:
        print("## commits：无")
    print()

    contribs = api(f"/repos/{o}/{r}/contributors", {"per_page": 10})
    if contribs:
        names = ", ".join(f"{c.get('login')}({c.get('contributions')})" for c in contribs)
        mark = "（当前页 10 条，是否还有更多未确认）" if len(contribs) == 10 else ""
        print(f"## contributors{mark}: {names}\n")

    readme = api(f"/repos/{o}/{r}/readme", raw=True)
    print(f"## README（前 {args.readme_chars} 字符）")
    if readme is None:
        print("README 未取得，端点不存在或不可访问；内容未确认")
    elif readme:
        print(readme[:args.readme_chars])
        if len(readme) > args.readme_chars:
            print("\n…（已截断）")
    else:
        print("README 返回空内容")
    print()

    issue_page = api(f"/repos/{o}/{r}/issues",
                     {"state": "open", "per_page": min(args.max_issues, 100), "sort": "updated", "direction": "desc"})
    if issue_page is None:
        print("## open issues：端点不可访问，issue 情况未确认")
        return
    issues = [i for i in issue_page if "pull_request" not in i]
    print(f"## open issues（更新倒序样本：API 返回 {len(issue_page)} 条 issue/PR，其中 {len(issues)} 条 issue）")
    print("仅当前页，未翻页；不能据此判断 issue 总数或问题出现频率。")
    if not issues:
        print("当前页没有 issue 样本，仓库是否存在其他 open issue 未确认。")
    for i in issues:
        labels = ",".join(l["name"] for l in i.get("labels", []))
        labels = f"[{labels}]" if labels else ""
        source = f"[#{i['number']}]({i['html_url']})" if i.get("html_url") else f"#{i['number']}"
        print(f"- {source} {i['title'][:70]} {labels} 评论{ i.get('comments', 0)} 更新{i.get('updated_at', '')[:10]}")


def cmd_rate(_):
    d = api("/rate_limit")
    for k in ("core", "search"):
        rr = d["resources"][k]
        reset = dt.datetime.fromtimestamp(rr["reset"], dt.timezone.utc).astimezone().strftime("%H:%M:%S")
        print(f"{k}: 剩余 {rr['remaining']}/{rr['limit']}，{reset} 重置")


def main():
    for stream in (sys.stdout, sys.stderr):
        if stream.encoding and stream.encoding.lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__,
                               formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("search", help="搜索仓库，输出候选池表格")
    ps.add_argument("query")
    ps.add_argument("--top", type=int, default=30)
    ps.add_argument("--sort", choices=["stars", "best", "forks", "updated"], default="stars")
    pi = sub.add_parser("inspect", help="拉取单个仓库的维护证据样本（6 次请求，不翻页）")
    pi.add_argument("repo", help="owner/repo")
    pi.add_argument("--max-issues", type=int, default=20, help="单页 issue/PR 混合样本条数，最多 100（默认 20）")
    pi.add_argument("--readme-chars", type=int, default=4000)
    sub.add_parser("rate", help="查看 API 限额")
    args = p.parse_args()
    before = REQUEST_ATTEMPTS
    try:
        {"search": cmd_search, "inspect": cmd_inspect, "rate": cmd_rate}[args.cmd](args)
    finally:
        print(f"HTTP 请求尝试：{REQUEST_ATTEMPTS - before} 次（含失败和限速重试）", file=sys.stderr)


if __name__ == "__main__":
    main()
