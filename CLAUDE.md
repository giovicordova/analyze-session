# analyze-session

Plugin for analyzing and fixing Claude Code session performance, token usage, cost, and tool efficiency.

## Structure

```
analyze-session/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── analyze-session/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── analyze.py
│   └── fix-session/
│       ├── SKILL.md
│       └── scripts/
│           └── fix-report.py
├── CLAUDE.md
├── README.md
└── VISION.md
```

## Skills

- `/analyze-session:analyze-session` — Analyze a session or project. Outputs `SESSION-ANALYSIS.md` at the project root.
- `/analyze-session:fix-session` — Read a report and guide fixes interactively.

## Testing

Run `/analyze-session:analyze-session` in any Claude Code session to exercise the skill end-to-end.

## Conventions

- Python stdlib only — no pip dependencies
- Cost calculations use per-message transcript data, falling back to session-meta aggregates
- The analyze skill runs in a forked subagent context (`context: fork`) to keep the user's main context clean
- Reports are saved as `SESSION-ANALYSIS.md` (all caps) at the project root
