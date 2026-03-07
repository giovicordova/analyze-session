# analyze-session

Claude Code plugin that analyzes session performance, token costs, cache efficiency, tool usage, and quality metrics. Produces actionable Markdown reports.

See README.md for full documentation.

## Plugin structure

```
.claude-plugin/plugin.json   — plugin manifest
skills/analyze/SKILL.md      — skill definition
skills/analyze/scripts/      — Python scripts (analyze.py, fix-report.py, run-analysis.sh)
hooks/hooks.json.example     — Stop hook example for auto-analysis
tests/                       — report validation
```

## Usage

- `/analyze-session:analyze` — analyze a session or project → `SESSION-ANALYSIS.md`
- `/analyze-session:analyze --fix` — read a report and guide fixes interactively
- `/analyze-session:analyze --fix --apply` — auto-apply low-risk fixes

## Testing

- Run `/analyze-session:analyze` in any Claude Code session to exercise end-to-end.
- Run `python3 tests/validate-report.py tests/sample-report.md` to validate report parsing.

## Conventions

- Python stdlib only — no pip dependencies
- Cost calculations use per-message transcript data, falling back to session-meta aggregates
- The analyze skill runs in a forked subagent context (`context: fork`) to keep the user's main context clean
- Reports are saved as `SESSION-ANALYSIS.md` (all caps) at the project root
