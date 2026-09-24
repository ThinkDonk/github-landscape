# GitHub Landscape

**English** | [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: standard library only](https://img.shields.io/badge/Python-standard_library_only-3776AB.svg)](scripts/gh.py)

A Codex skill for researching similar open-source projects on GitHub. Compare feature coverage, maintenance evidence, and practical limitations to decide what to reuse, adapt, or build.

The skill guides the research; a standalone Python helper collects repository data from the GitHub REST API. The helper uses only the Python standard library and can run without Codex.

## What it helps with

- Find existing projects for an idea or a concrete set of requirements.
- Compare relevant candidates with links to the evidence behind each conclusion.
- Separate repository activity from software quality and suitability.
- Distinguish confirmed limitations from capabilities that have not been verified.
- Explain when reuse, adaptation, or a new implementation makes sense.

This is a cross-project research workflow. Single-repository code audits, drop-in dependency selection, and academic literature reviews are outside its scope. GitHub supply alone does not establish market demand or commercial viability.

## Requirements

- Python 3 with access to `https://api.github.com`; no `pip install` is needed.
- Git to use the clone commands below, or download and extract the repository ZIP.
- Codex with local skills support to use the guided research workflow.
- Optional: a `GITHUB_TOKEN` environment variable for authenticated API requests. Actual limits depend on GitHub's response.

The skill instructions and CLI messages are currently written in Simplified Chinese. The skill instructs the agent to deliver its analysis in the user's language, including English; the standalone CLI has no language switch.

## Install as a Codex skill

Clone into your personal skills directory.

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

For a project-scoped installation, place the folder at `<your-project>/.agents/skills/github-landscape/`. Keep `SKILL.md` and `scripts/` together. If the skill does not appear, restart Codex. See the [official skill documentation](https://learn.chatgpt.com/docs/build-skills) for discovery paths and invocation details.

In Codex CLI or the IDE extension, invoke it with `$github-landscape`:

```text
$github-landscape I want to build a self-hosted notes app with offline editing,
Markdown export, and multi-device sync. Research similar public GitHub projects,
compare their feature coverage and maintenance evidence, and explain what I could reuse.
Please answer in English and link the sources behind key claims.
```

In clients with a skill picker, select **github-landscape** and describe your requirements.

## Use the Python helper directly

Clone the repository into a working directory, then run commands from its root:

```bash
git clone https://github.com/ThinkDonk/github-landscape.git
cd github-landscape
python scripts/gh.py --help
python scripts/gh.py search "cli note taking" --top 30
python scripts/gh.py search "cli note taking" --sort best
python scripts/gh.py inspect owner/repo --max-issues 20 --readme-chars 4000
python scripts/gh.py rate
```

Replace `owner/repo` with a real repository, such as `cli/cli`. Use `python3` on systems where that is the Python 3 command, or `py -3` on Windows if you use the Python launcher. If you already installed the skill, you can run these commands from that installation directory without cloning again.

| Command | Output | Options |
| --- | --- | --- |
| `search "query"` | Markdown candidate table with repository links and metadata | `--top`: default 30, capped at 100; `--sort`: `stars` (default), `best`, `forks`, or `updated` |
| `inspect owner/repo` | Repository metadata, releases, default-branch commits, contributors, a README excerpt, and open issue samples | `--max-issues`: default 20, capped at 100 mixed issue/PR entries; `--readme-chars`: default 4000 |
| `rate` | Remaining core/search API quota and reset times | No options |

Use positive values for sample sizes and README length. Set `GITHUB_TOKEN` in the process environment if needed; the script does not read `.env` files or GitHub CLI credentials automatically.

Report content goes to standard output. Rate-limit messages and actual HTTP request attempts go to standard error. To save a sample:

```bash
python scripts/gh.py inspect cli/cli > repository-sample.md
```

The helper collects evidence; it does not automatically select a shortlist or write the final comparative analysis.

## Research output

The guided workflow normally responds in the conversation. A report covers the search date and scope, representative candidates, feature coverage, maintenance and quality evidence, specific limitations, recommendations, and unresolved questions. Key claims link to their sources, with facts, maintainer statements, and analysis distinguished.

Feature comparisons use four states: **confirmed support**, **partial support**, **confirmed lack of support**, and **unconfirmed**. A missing README mention is unconfirmed, not proof that a feature is absent.

When a file is requested, use the task's output directory. A suggested fallback is `outputs/landscape-{slug}-{YYYYMMDD}.md` in the working project, outside the installed skill directory.

## Evidence and API limits

- **No pagination:** search and inspection collect limited samples. Inspection requests up to 5 releases, 15 default-branch commits, 10 contributors, a README excerpt, and one open issue/PR page.
- **Issues include pull requests:** GitHub's `open_issues_count` includes PRs. `--max-issues` limits mixed entries before PRs are filtered out; an empty filtered page does not mean the repository has no open issues.
- **Issue reports are individual reports:** samples ordered by recent updates cannot establish defect frequency or prove a reported bug was reproduced.
- **Releases are sampled:** only non-draft entries with publication timestamps count as confirmed published releases. Stable releases and prereleases are distinguished and sorted within the sample; the latest stable release across the whole repository is not guaranteed to be included.
- **README content may be truncated:** missing details remain unconfirmed and may require additional research.
- **Activity is not a quality score:** stars indicate attention and push dates indicate activity. Neither alone proves quality, suitability, or abandonment.
- **Request accounting is per command:** without retries, `search` and `rate` make 1 request each; a complete `inspect` makes 6. Each endpoint allows at most 5 attempts. Two to four searches plus three to five inspections therefore have a baseline of 20–34 requests, excluding extra checks and retries. There is no automatic cross-command total or enforced workflow budget.

## Project layout

```text
github-landscape/
├── SKILL.md             # Research instructions and evidence boundaries
├── scripts/gh.py        # Standard-library GitHub API helper
├── tests/test_gh.py      # Offline regression tests
├── README.md            # English documentation
├── README.zh-CN.md      # Simplified Chinese documentation
└── LICENSE              # MIT license
```

## Development and contributions

Run the existing tests from the repository root:

```bash
python -m unittest discover -s tests -v
```

The tests mock HTTP/API calls and require no network access or token. They check sampled-evidence interpretation, missing data, PR filtering, and request accounting; they do not validate live GitHub availability or the quality of an agent's full research report.

[Issues](https://github.com/ThinkDonk/github-landscape/issues) and [pull requests](https://github.com/ThinkDonk/github-landscape/pulls) in English or Chinese are welcome. Include the command or research prompt, expected and actual behavior, and source links when reporting an evidence problem. Keep both READMEs aligned when updating user-facing behavior, and add focused regression coverage for script changes. Remove tokens from shared logs.

## License

Licensed under the [MIT License](LICENSE). Copyright (c) 2026 ThinkDonk.

The license covers this repository's code and documentation. Projects examined during research retain their own licenses.
