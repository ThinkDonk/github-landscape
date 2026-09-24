# GitHub Landscape

[English](README.md) | **简体中文**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: standard library only](https://img.shields.io/badge/Python-standard_library_only-3776AB.svg)](scripts/gh.py)

一个用于调研 GitHub 同类开源项目的 Codex 技能。通过比较功能覆盖、维护证据与实际限制，帮助你决定哪些部分可以复用、改造或自行实现。

技能负责指导调研流程，独立的 Python 辅助脚本通过 GitHub REST API 收集仓库数据。脚本仅依赖 Python 标准库，也可以脱离 Codex 单独使用。

## 能解决什么问题

- 根据项目想法或具体需求，寻找已有的公开实现。
- 比较相关候选，为关键结论提供可追溯的来源链接。
- 区分仓库活跃度、软件质量与需求适配程度。
- 区分已经证实的限制与仍未确认的能力。
- 说明在什么条件下适合复用、改造或自建。

本项目用于跨项目的横向调研，不用于单仓库代码审计、可直接引入的依赖选型或学术论文综述。GitHub 上的项目供给不能单独证明市场需求或商业可行性。

## 环境要求

- Python 3，并能访问 `https://api.github.com`；无需执行 `pip install`。
- 使用下方克隆命令需要 Git，也可以下载仓库 ZIP 后解压。
- 使用完整调研流程需要支持本地技能的 Codex。
- 可选：通过环境变量 `GITHUB_TOKEN` 发起认证 API 请求；实际额度以 GitHub 响应为准。

当前技能指令和命令行提示使用简体中文。技能要求智能体按用户的语言交付分析，因此可以要求英文报告；独立命令行脚本暂未提供语言切换功能。

## 安装为 Codex 技能

将仓库克隆到个人技能目录。

**macOS / Linux**

```bash
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/ThinkDonk/github-landscape.git "$HOME/.agents/skills/github-landscape"
```

**Windows PowerShell**

```powershell
New-Item -ItemType Directory -Force -Path "$HOME/.agents/skills" | Out-Null
git clone https://github.com/ThinkDonk/github-landscape.git "$HOME/.agents/skills/github-landscape"
```

如需仅对某个项目生效，可将目录放在 `<你的项目>/.agents/skills/github-landscape/`。保持 `SKILL.md` 与 `scripts/` 的相对位置不变。若技能未出现，请重启 Codex。技能发现路径与调用方式可参考 [OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills)。

在 Codex CLI 或 IDE 扩展中，通过 `$github-landscape` 调用：

```text
$github-landscape 我想做一个可以自托管的笔记应用，需要离线编辑、
Markdown 导出和多设备同步。请调研 GitHub 上相似的公开项目，
比较功能覆盖与维护证据，说明哪些部分可以复用，并为关键结论附上来源链接。
```

在提供技能选择器的客户端中，选择 **github-landscape**，再描述需求即可。

## 直接使用 Python 脚本

将仓库克隆到工作目录，然后在仓库根目录执行：

```bash
git clone https://github.com/ThinkDonk/github-landscape.git
cd github-landscape
python scripts/gh.py --help
python scripts/gh.py search "cli note taking" --top 30
python scripts/gh.py search "cli note taking" --sort best
python scripts/gh.py search "cli note taking" "terminal notes in:readme" --sort best --top 30
python scripts/gh.py search "cli note taking" "terminal notes in:readme" --format json
python scripts/gh.py inspect owner/repo --max-issues 20 --readme-chars 4000
python scripts/gh.py inspect owner/repo --format json
python scripts/gh.py issues owner/repo "resume download" --state all --top 20
python scripts/gh.py issue owner/repo 123 --max-comments 20 --format json
python scripts/gh.py rate
```

将 `owner/repo` 替换为真实仓库，例如 `cli/cli`。如果系统的 Python 3 命令是 `python3`，请替换示例中的 `python`；Windows 使用 Python 启动器时也可以改为 `py -3`。如果已经安装技能，可以直接在安装目录执行这些命令，无需重复克隆。

| 命令 | 输出 | 参数 |
| --- | --- | --- |
| `search "query" ["query" ...]` | 合并后的 Markdown 候选表，包含仓库链接、元数据与命中查询编号 | `--top`：每条查询默认 30，最多 100；`--sort`：`stars`（默认）、`best`、`forks` 或 `updated` |
| `inspect owner/repo` | 仓库元数据、发布版本、默认分支提交、贡献者、README 摘要及 open issue 样本 | `--max-issues`：默认 20，最多 100 条 issue/PR 混合条目；`--readme-chars`：默认 4000 |
| `issues owner/repo "keywords"` | 按功能搜索 Issue，返回正文摘录、状态、时间、作者与来源链接 | `--state`：`all`（默认）、`open`、`closed`；`--top`：默认 20，最多 100；`--sort`：`best`（默认）、`updated`；`--body-chars`：默认 2000 |
| `issue owner/repo 123` | 选中 Issue 的正文与第一页评论 | `--max-comments`：默认 20，最多 100；`--body-chars`：正文及每条评论默认各截取 4000 字符 |
| `rate` | core/search API 的剩余额度与重置时间 | 支持下文的 `--format` |

所有命令均支持 `--format markdown`（默认）或 `--format json`。

样本条数和 README 长度请使用正数。需要认证时，在进程环境中设置 `GITHUB_TOKEN`；脚本不会自动读取 `.env` 文件或 GitHub CLI 的登录凭据。

报告内容写入标准输出，限速提示与实际 HTTP 请求尝试数写入标准错误。可以重定向保存样本：

```bash
python scripts/gh.py inspect cli/cli > repository-sample.md
```

脚本负责收集证据，不会自动筛选最终候选或撰写完整对比分析。

多条查询分别执行后按仓库 ID 去重，保留首次出现的元数据与展示顺序，并用 `Q1`、`Q2` 等记录全部命中查询。去除首尾空白后相同的查询只执行一次。`--top` 对每条查询生效，不限制合并后的总数。命中次数仅表示来源，不是适配评分；各查询的结果总数有重叠，不能直接相加。

某条查询失败时，输出仍保留成功结果，命令退出码为 1。查询本身的错误不阻止其他查询；连接、认证或限额耗尽等故障会停止后续查询并标记跳过。GitHub 的 `incomplete_results` 标记会单独提示；请求成功不代表检索覆盖完整。

### JSON 输出

```bash
python scripts/gh.py search "cli note taking" "terminal notes in:readme" --format json > candidates.json
python scripts/gh.py inspect cli/cli --format json > repository-sample.json
```

标准输出包含一个 JSON 文档，诊断与 HTTP 尝试数仍写入标准错误。公共字段包括 `schema_version`（当前为 `1`）、`command`、`collected_at`（UTC）、`request_attempts`（含重试）和 `status`（`ok`、`partial` 或 `error`）。状态描述数据取得情况，不代表覆盖完整或证据质量。API 故障仍输出 JSON，退出码为 1；CLI 参数错误可能仅输出诊断。

- **搜索：**`queries` 保留每条查询的编号、文本、来源 URL、尝试时间、状态、总数/返回数、样本上限、`truncated` 和 GitHub 的 `incomplete_results`。失败或跳过的查询保留错误，不填写结果数量。`repositories` 为 GitHub 元数据加 `matched_queries`；`unique_count` 仅统计实际取得并去重后的仓库。`truncated` 比较 GitHub 总数与本页返回数，不能替代独立的 `incomplete_results` 标记。
- **检查：**`repository`、`releases`、`commits`、`contributors`、`readme`、`issues` 各自包含 `status`、`source_url`、`collected_at` 和 `data`。未取得的数据为 `null`，与成功返回的空列表或空文本不同。分节状态为 `ok`、`unavailable`、`error` 或 `skipped`。保留已取得的部分结果；任一分节不可访问或失败时退出码为 1。
- **样本：**列表分节记录 `sample_limit`、`returned_count`、`paginated: false` 和 `limit_reached`。满页不能证明还有下一页。README 记录 `character_limit`、`original_characters` 与 `truncated`。Issues 保留 API 混合返回数和 `pull_requests_excluded`，`data` 仅包含 issue。Releases 保留原始 `draft`、`prerelease` 与发布字段，使用方仍须遵守下文的发布判断规则。
- **额度：**`rate_limit.data` 保存 GitHub 的资源额度响应，并带有相同的来源/状态信息。跳过的端点未发起请求，采集时间为 `null`。
- **定向 Issue：**`issues` 返回实际执行的 `query`，以及包含来源/状态、计数、样本标记和 `data` 条目的 `issues` 分节。`issue` 返回 `issue` 与 `comments` 分节。正文摘录保留原始字段，并增加 `body_character_limit`、`body_original_characters`、`body_truncated`。评论记录 `order: "id_asc"`、Issue 元数据中的 `reported_total` 及返回样本数，评论页的 `truncated` 比较这两个数量。缺失或未提供的正文为 `null`，与返回空字符串不同。

### 针对某项功能取证

```bash
python scripts/gh.py issues cli/cli "extension" --state all --top 5
python scripts/gh.py issues cli/cli "extension" --state closed --sort updated --format json
python scripts/gh.py issue owner/repo 123 --max-comments 20 --body-chars 4000
```

先在相关仓库中按功能关键词检索，再将 `owner/repo` 和 `123` 替换为从结果中选出的仓库与 Issue 编号。搜索范围包括标题、正文和评论；结果包含 Issue 正文，不会返回所有命中评论。命令固定仓库与 Issue 类型，默认同时包含 open、closed，并排除 PR。可通过 `--state` 缩小状态范围。不允许关键词覆盖仓库/类型/状态/搜索字段（`repo:`、`org:`、`user:`、`is:`、`type:`、`state:`、`in:`），也不支持布尔运算符（`AND`、`OR`、`NOT`）；同义词请分别搜索。

仅在评论会改变判断时读取选中 Issue 的讨论。评论端点按 ID 升序返回第一页，可能缺少后续回复或最终决定；需要时增加样本/字符上限，或沿来源链接补查。`closed` 与 `state_reason` 不能单独证明已修复、已发布或功能已支持。未命中不代表不存在，个案也不证明已复现或问题频率。`issue` 会拒绝 PR 编号；评论请求失败时仍保留 Issue 正文，状态为 `partial`，退出码为 1。

底层 API 说明：[Issue 搜索](https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests)、[Issue 详情](https://docs.github.com/en/rest/issues/issues#get-an-issue)、[Issue 评论](https://docs.github.com/en/rest/issues/comments#list-issue-comments)。

## 调研结果包含什么

完整调研流程默认在对话中交付结果，包括检索日期与范围、代表候选、功能覆盖、维护与质量证据、具体限制、建议及未确认项。关键主张附直接来源链接，并区分事实、维护者声明与分析推断。

功能比较使用四种状态：**已证实支持**、**部分支持**、**已证实不支持**和**未确认**。README 没有提及某项能力时，应标为“未确认”，不能直接认定为不支持。

需要文件时，遵循当前任务的输出目录；未指定时，可保存到工作项目内的 `outputs/landscape-{slug}-{YYYYMMDD}.md`，不要写入技能安装目录。

## 证据与 API 边界

- **不翻页：**仓库搜索、检查、定向 Issue 搜索和评论读取仅获取有限样本。检查最多请求 5 条 release、15 条默认分支提交、10 位贡献者、一段 README 和一页 open issue/PR。
- **issue 计数包含 PR：**GitHub 的 `open_issues_count` 包含 PR。`--max-issues` 限制过滤前的混合条目数；过滤后为空，不代表仓库没有 open issue。
- **issue 属于个案报告：**按最近更新时间抽样，不能推导问题发生频率，也不能证明报告中的问题已经复现。
- **release 属于样本：**仅将有发布时间的非草稿记录计为已确认发布，区分正式版和预发布，并在样本内按发布时间排序；不保证包含全仓库最新正式版。
- **README 可能被截断：**缺少的信息仍属于未确认，关键判断可能需要补充调查。
- **活跃度不是质量评分：**stars 表示关注度，push 日期表示活动时间，两者都不能单独证明质量、适配程度或停止维护。
- **请求计数按命令统计：**无重试时，`search` 每条不同查询请求 1 次，`rate` 和 `issues` 各请求 1 次，完整执行 `inspect` 请求 6 次，`issue` 最多请求 2 次（正文与评论）。每个端点最多尝试 5 次。2–4 条搜索查询加 3–5 次检查的基线为 20–34 次请求，定向 Issue 取证、其他补查与重试另计。脚本不自动跨命令汇总，也没有全流程预算硬限制。

## 项目结构

```text
github-landscape/
├── SKILL.md             # 调研指令与取证边界
├── scripts/gh.py        # 仅依赖标准库的 GitHub API 辅助脚本
├── tests/test_gh.py      # 离线回归测试
├── README.md            # 英文说明
├── README.zh-CN.md      # 简体中文说明
└── LICENSE              # MIT 协议
```

## 开发与贡献

在仓库根目录执行已有测试：

```bash
python -m unittest discover -s tests -v
```

测试模拟 HTTP/API 调用，不需要联网或 token，覆盖多查询去重与来源保留、JSON 解析与证据边界、定向 Issue 查询与评论采样、部分失败、样本解释、数据缺失、PR 过滤和请求计数；不验证 GitHub 实时可用性，也不代表已经验证智能体完整调研报告的质量。

欢迎使用中文或英文提交 [Issue](https://github.com/ThinkDonk/github-landscape/issues) 和 [Pull Request](https://github.com/ThinkDonk/github-landscape/pulls)。反馈时请提供命令或调研提示词、预期结果与实际表现；证据判断问题请附来源链接。修改面向用户的行为时同步两份 README，修改脚本时补充有针对性的回归测试。分享日志前请去除 token。

## 开源协议

本项目采用 [MIT License](LICENSE)，版权所有 (c) 2026 ThinkDonk。

协议适用于本仓库的代码与文档；调研涉及的其他项目仍遵循各自的许可证。正式条款见 `LICENSE` 中的英文原文。
