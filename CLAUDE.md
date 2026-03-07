# analyze-session

Plugin for analyzing and fixing Claude Code session performance, token usage, cost, and tool efficiency.

See README.md for project overview and usage.

## Skills

- `/analyze-session:analyze` — Analyze a session or project. Outputs `SESSION-ANALYSIS.md` at the project root.
- `/analyze-session:analyze --fix` — Read a report and guide fixes interactively.
- `/analyze-session:analyze --fix --apply` — Auto-apply low-risk fixes.

## Testing

- Run `/analyze-session:analyze` in any Claude Code session to exercise the skill end-to-end.
- Run `python3 tests/validate-report.py tests/sample-report.md` to validate report parsing.

## Conventions

- Python stdlib only — no pip dependencies
- Cost calculations use per-message transcript data, falling back to session-meta aggregates
- The analyze skill runs in a forked subagent context (`context: fork`) to keep the user's main context clean
- Reports are saved as `SESSION-ANALYSIS.md` (all caps) at the project root
