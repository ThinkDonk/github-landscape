---
name: github-landscape
description: GitHub 同类项目调研：给定项目想法或需求描述，搜索 GitHub 公开仓库找出同类项目，按硬标准评估维护状态与质量，输出横向对比、各自不足与市场缺口结论。当用户说"这个想法有人做过吗"、"帮我调研同类开源项目"、"GitHub 上有哪些类似项目"、"开源竞品调研"、"项目预研"、"find similar open source projects"时使用。不适用于：单仓库深度分析（读代码/复盘历史）、找可直接引入的依赖库（选型）、学术论文调研。
---

# GitHub Landscape

一句话需求 → 找出 GitHub 同类项目 → 判断哪些仍在维护、做得好 → 汇总各自不足与市场缺口 → 给出「是否值得自己做」的结论。

数据获取全部通过 `scripts/gh.py`（相对本 skill 目录，零依赖 Python 3，匿名可用），模型只做判断与分析，不裸调 API。

## 流程

### 1. 关键词与搜索

- 从需求提炼 2-4 组英文关键词（GitHub 搜索以英文为主；面向中文用户的项目可补一轮中文关键词）
- `python scripts/gh.py search "<query>" --top 30`
- query 支持 GitHub 限定符：`language:python`、`topic:cli` 等；维护过滤交给阶段 2 的硬标准，不在 query 里预设 `pushed:>`
- 多组关键词可合并成一次 Bash 调用；输出去重合并成候选池（约 20-40 个）
- 结果过少时换同义词、拆功能词、去掉限定符再搜，而不是空手进入下一阶段
- 小众相关项目被 star 排序淹没时，可用 `--sort best`（最佳匹配）补一轮

### 2. 维护度与质量打分（硬标准，不自由发挥）

| 判定 | 标准 |
|------|------|
| 出局 | archived=true，或 README 明确声明 deprecated/unmaintained |
| 活跃 | pushed_at ≤ 6 个月，或近 12 个月有 release |
| 缓慢 | pushed_at 6-12 个月 |
| 停滞 | pushed_at > 12 个月 |

质量档位：stars（<100 / 100-1k / 1k-10k / >10k）、license 有无、topics 与 README 完整度。

候选池按「活跃优先、star 降序」选出 top 3-5 进入阶段 3。停滞项目除非是需求核心参考否则不深入，但在报告里保留名字（「这个方向的老项目都死了」本身就是信号）。

### 3. 深度分析

- `python scripts/gh.py inspect owner/repo`（一次拉全：概况 / releases / commits / contributors / README / open issues）
- 功能覆盖矩阵：先从需求提炼 5-8 个功能维度，逐项目标 ✓ / 部分 / ✗
- 各自不足的三个来源：README 未覆盖的能力、open issues 里的高频抱怨与 feature request、技术栈与架构限制

### 4. 缺口汇总与结论

报告落盘 `./landscape-reports/{slug}-{date}.md`（slug 取需求核心词，date 为 YYYYMMDD）。结论三选一：

- 市场饱和：头部项目活跃且覆盖完整，不建议做
- 有缺口：给出缺口清单 + 差异化方向
- 数据不足：说明缺什么、需要用户补充什么

## 报告模板

1. 元信息：日期、需求一句话、关键词组
2. 候选池总表（search 输出整理）
3. 横向对比表：项目 | stars | 维护判定 | 质量档位 | 一句话定位
4. 功能覆盖矩阵（维度 × 项目）
5. 各项目不足（逐项，注明证据来源）
6. 缺口与机会（跨项目汇总）
7. 结论
8. 数据与置信度：哪些是 API 事实、哪些是推断

## 铁律

| 规则 | 内容 |
|------|------|
| 数据走脚本 | search 返回已含 stars/forks/pushed_at/license/archived，禁止逐仓库裸 curl 重拉对比表数据 |
| 判定走硬标准 | 维护度只按上表时间线判定，不凭印象 |
| 事实与推断分离 | 报告末节必须区分 API 事实与模型推断 |
| 不足要有证据 | 每条不足注明来源（README 缺失 / issue #N / 技术栈限制），不编 |

## 边界

- 限速：匿名 search 10 次/分钟，脚本已内置退避；整个流程默认 ≤ 15 个请求
- `GITHUB_TOKEN` 环境变量可选，设置后限额提升
- 单仓库深度分析（读代码、历史复盘）不在本 skill 范围
- 报告用中文写
