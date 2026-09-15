# github-landscape

GitHub 同类项目调研 skill：给定一个项目想法 → 搜索 GitHub 公开仓库找出同类项目 → 按硬标准评估维护状态与质量 → 输出横向对比、各自不足与市场缺口结论，回答「这个想法有人做过吗、还值得做吗」。

## 组成

- `SKILL.md` — skill 本体：流程、维护度判定标准、报告模板
- `scripts/gh.py` — 数据层（零依赖 Python 3）：
  - `search "<query>"` 搜仓库，输出候选池表格（含 stars/push 天数/license/存档）
  - `inspect <owner/repo>` 一次拉全单仓库指标（概况/releases/commits/contributors/README/open issues）
  - `rate` 查 API 限额

## 维护度判定（硬标准）

| 判定 | 标准 |
|------|------|
| 出局 | archived，或声明弃坑 |
| 活跃 | pushed ≤ 6 个月，或近 12 个月有 release |
| 缓慢 | pushed 6-12 个月 |
| 停滞 | pushed > 12 个月 |

## 使用

```bash
python scripts/gh.py search "cli note taking" --top 30
python scripts/gh.py inspect mickael-kerjean/nu
python scripts/gh.py rate
```

匿名即可用（search 限 10 次/分钟，脚本自动退避）；设置 `GITHUB_TOKEN` 环境变量可提升限额。

## 报告输出

调研报告落盘到当前工作目录 `./landscape-reports/{slug}-{date}.md`，结构：候选池总表 → 横向对比 → 功能覆盖矩阵 → 各项目不足（带证据）→ 缺口与机会 → 结论。
