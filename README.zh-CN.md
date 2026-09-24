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
python scripts/gh.py inspect owner/repo --max-issues 20 --readme-chars 4000
python scripts/gh.py rate
```

将 `owner/repo` 替换为真实仓库，例如 `cli/cli`。如果系统的 Python 3 命令是 `python3`，请替换示例中的 `python`；Windows 使用 Python 启动器时也可以改为 `py -3`。如果已经安装技能，可以直接在安装目录执行这些命令，无需重复克隆。

| 命令 | 输出 | 参数 |
| --- | --- | --- |
| `search "query" ["query" ...]` | 合并后的 Markdown 候选表，包含仓库链接、元数据与命中查询编号 | `--top`：每条查询默认 30，最多 100；`--sort`：`stars`（默认）、`best`、`forks` 或 `updated` |
| `inspect owner/repo` | 仓库元数据、发布版本、默认分支提交、贡献者、README 摘要及 open issue 样本 | `--max-issues`：默认 20，最多 100 条 issue/PR 混合条目；`--readme-chars`：默认 4000 |
| `rate` | core/search API 的剩余额度与重置时间 | 无参数 |

样本条数和 README 长度请使用正数。需要认证时，在进程环境中设置 `GITHUB_TOKEN`；脚本不会自动读取 `.env` 文件或 GitHub CLI 的登录凭据。

报告内容写入标准输出，限速提示与实际 HTTP 请求尝试数写入标准错误。可以重定向保存样本：

```bash
python scripts/gh.py inspect cli/cli > repository-sample.md
```

脚本负责收集证据，不会自动筛选最终候选或撰写完整对比分析。

多条查询分别执行后按仓库 ID 去重，保留首次出现的元数据与展示顺序，并用 `Q1`、`Q2` 等记录全部命中查询。去除首尾空白后相同的查询只执行一次。`--top` 对每条查询生效，不限制合并后的总数。命中次数仅表示来源，不是适配评分；各查询的结果总数有重叠，不能直接相加。

某条查询失败时，输出仍保留成功结果，命令退出码为 1。查询本身的错误不阻止其他查询；连接、认证或限额耗尽等故障会停止后续查询并标记跳过。GitHub 的 `incomplete_results` 标记会单独提示；请求成功不代表检索覆盖完整。

## 调研结果包含什么

完整调研流程默认在对话中交付结果，包括检索日期与范围、代表候选、功能覆盖、维护与质量证据、具体限制、建议及未确认项。关键主张附直接来源链接，并区分事实、维护者声明与分析推断。

功能比较使用四种状态：**已证实支持**、**部分支持**、**已证实不支持**和**未确认**。README 没有提及某项能力时，应标为“未确认”，不能直接认定为不支持。

需要文件时，遵循当前任务的输出目录；未指定时，可保存到工作项目内的 `outputs/landscape-{slug}-{YYYYMMDD}.md`，不要写入技能安装目录。

## 证据与 API 边界

- **不翻页：**搜索和检查仅获取有限样本。检查最多请求 5 条 release、15 条默认分支提交、10 位贡献者、一段 README 和一页 open issue/PR。
- **issue 计数包含 PR：**GitHub 的 `open_issues_count` 包含 PR。`--max-issues` 限制过滤前的混合条目数；过滤后为空，不代表仓库没有 open issue。
- **issue 属于个案报告：**按最近更新时间抽样，不能推导问题发生频率，也不能证明报告中的问题已经复现。
- **release 属于样本：**仅将有发布时间的非草稿记录计为已确认发布，区分正式版和预发布，并在样本内按发布时间排序；不保证包含全仓库最新正式版。
- **README 可能被截断：**缺少的信息仍属于未确认，关键判断可能需要补充调查。
- **活跃度不是质量评分：**stars 表示关注度，push 日期表示活动时间，两者都不能单独证明质量、适配程度或停止维护。
- **请求计数按命令统计：**无重试时，`search` 每条不同查询请求 1 次，`rate` 请求 1 次，完整执行 `inspect` 请求 6 次。每个端点最多尝试 5 次。2–4 条搜索查询加 3–5 次检查的基线为 20–34 次请求，补查和重试另计。脚本不自动跨命令汇总，也没有全流程预算硬限制。

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

测试模拟 HTTP/API 调用，不需要联网或 token，覆盖多查询去重与来源保留、部分失败、样本解释、数据缺失、PR 过滤和请求计数；不验证 GitHub 实时可用性，也不代表已经验证智能体完整调研报告的质量。

欢迎使用中文或英文提交 [Issue](https://github.com/ThinkDonk/github-landscape/issues) 和 [Pull Request](https://github.com/ThinkDonk/github-landscape/pulls)。反馈时请提供命令或调研提示词、预期结果与实际表现；证据判断问题请附来源链接。修改面向用户的行为时同步两份 README，修改脚本时补充有针对性的回归测试。分享日志前请去除 token。

## 开源协议

本项目采用 [MIT License](LICENSE)，版权所有 (c) 2026 ThinkDonk。

协议适用于本仓库的代码与文档；调研涉及的其他项目仍遵循各自的许可证。正式条款见 `LICENSE` 中的英文原文。
