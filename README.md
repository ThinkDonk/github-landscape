# github-landscape

比较 GitHub 上与需求相似的公开项目，用可追溯证据说明功能覆盖、维护情况和限制，辅助复用、改造或自建决策。它不做单仓库代码审计，不把 GitHub 供给当作市场需求证明。

## 组成与使用

- `SKILL.md`：适用范围、取证边界与分析规则。
- `scripts/gh.py`：零依赖 Python 3 数据工具，优先复用其输出；允许用其他已有工具补证。
- `tests/test_gh.py`：mock HTTP/API 的离线回归测试。

```text
python scripts/gh.py search "cli note taking" --top 30
python scripts/gh.py search "cli note taking" --sort best
python scripts/gh.py inspect owner/repo --max-issues 20 --readme-chars 4000
python scripts/gh.py rate
python -m unittest discover -s tests -v
```

`GITHUB_TOKEN` 环境变量可选；额度以 GitHub 响应为准。脚本把报告内容写到标准输出，把限速提示和实际 HTTP 请求尝试数写到标准错误。无重试时 `search` 和 `rate` 各 1 次、`inspect` 为 6 次；每个端点最多尝试 5 次。因此 2–4 次搜索加 3–5 次 inspect 为 20–34 次基线请求，其他补查和重试另计。脚本没有全流程预算控制或自动跨命令合计。

## 数据边界

- stars 表示关注度；push 日期表示活动时间。两者都不是质量评分或停止维护的充分证据。
- 搜索和 inspect 均不翻页。`--max-issues` 控制单页 issue/PR 混合条目数（最多 100），不保证取得对应数量的纯 issue；过滤后为空不等于仓库没有 issue。
- `open_issues_count` 包含 PR。issue 内容属于个案报告，不能从按更新时间抽样的页面推导问题发生频率。
- releases 输出区分正式版和预发布，仅把有发布时间的非草稿纳入已发布样本，并在当前样本内按发布时间排序；不能据此保证找到了全仓库最新正式版。
- README 有截断；未提及的能力标为“未确认”，关键判断需要补查。
- 默认在对话中交付结果。需要文件时遵循当前任务的输出目录，具体结构随任务规模调整。
