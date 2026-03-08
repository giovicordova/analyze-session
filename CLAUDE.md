# analyze-session

Claude Code plugin that analyzes session performance, token costs, cache efficiency, tool usage, and quality metrics. Produces actionable Markdown reports.

See README.md for full documentation.

## Plugin structure

```
.claude-plugin/plugin.json   — plugin manifest
skills/run/SKILL.md          — skill definition
skills/run/scripts/          — Python scripts (analyze.py, fix-report.py, run-analysis.sh)
hooks/hooks.json.example     — Stop hook example for auto-analysis
tests/                       — report validation
```

## Usage

- `/sa:run` — analyze a session or project → `SESSION-ANALYSIS.md`
- `/sa:run --fix` — read a report and guide fixes interactively
- `/sa:run --fix --apply` — auto-apply low-risk fixes

## Testing

- Run `/sa:run` in any Claude Code session to exercise end-to-end.
- Run `python3 tests/validate-report.py tests/sample-report.md` to validate report parsing.

## Conventions

- Python stdlib only — no pip dependencies
- Cost calculations use per-message transcript data from `~/.claude/projects/` JSONL files
- The run skill runs in a forked subagent context (`context: fork`) to keep the user's main context clean
- Reports are saved as `SESSION-ANALYSIS.md` (all caps) at the project root
