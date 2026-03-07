# analyze-session

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugin that analyzes session performance, token costs, cache efficiency, tool usage, and quality metrics. Produces actionable Markdown reports from Claude Code's local data stores.

## What it does

- **Token & cost breakdown** with full cache detail (5-min ephemeral, 1-hour ephemeral, cache reads)
- **Tool usage** ranking with error tracking
- **Quality metrics** from Claude's self-assessed facets (outcome, helpfulness, friction)
- **Issue detection** with fix suggestions (high token turns, tool errors, cache cost, friction patterns)
- **Two scopes**: single-session deep dive or cross-session project trends
- **Fix companion**: reads the report, guides fixes, and auto-applies safe ones

## Install

Clone and load as a plugin:

```bash
git clone https://github.com/giovicordova/analyze-session.git
claude --plugin-dir ./analyze-session
```

No dependencies — uses Python stdlib only.

## Usage

### Analyze a session

```
/analyze-session:analyze
```

The report is saved as `SESSION-ANALYSIS.md` at the root of the project being analyzed.

### Fix issues from the report

```
/analyze-session:analyze --fix
```

### Auto-apply safe fixes

```
/analyze-session:analyze --fix --apply
```

### Options

| Param | Default | Description |
|-------|---------|-------------|
| `session_id` | `latest` | Session UUID or `latest` |
| `--project` | current directory | Project path to analyze |
| `--scope` | `session` | `session` for single session, `project` for all sessions |
| `--output` | `./SESSION-ANALYSIS.md` | Report output path |
| `--fix` | off | Switch to fix mode (reads existing report) |
| `--apply` | off | Auto-apply low-risk fixes (with `--fix`) |

### Examples

```
/analyze-session:analyze                                       # latest session, current project
/analyze-session:analyze latest --scope project                # all sessions for current project
/analyze-session:analyze abc123-def --project ~/myapp          # specific session, specific project
/analyze-session:analyze --fix                                 # discuss fixes from report
/analyze-session:analyze --fix --apply                         # auto-apply + discuss
```

### Standalone usage

The analysis scripts can also be run directly from a terminal or wired to a Claude Code hook:

```bash
# Run directly
./skills/analyze/scripts/run-analysis.sh --scope project

# Run and commit the report
./skills/analyze/scripts/run-analysis.sh --commit

# Run analysis + fix + auto-apply
./skills/analyze/scripts/run-analysis.sh --fix --apply
```

The plugin includes a Stop hook (`hooks/hooks.json`) that auto-runs analysis when a session ends. To disable it, remove or rename `hooks/hooks.json`.

To export the plugin as a zip for sharing:

```bash
./scripts/export-plugin.sh
```

## Sample output

### Single session

```
## Summary
| Field | Value |
|-------|-------|
| Total Cost | $4.14 |
| Model | claude-opus-4-6 |
| Outcome | mostly_achieved |

## Token Breakdown (Transcript)
| Category | Tokens | Cost |
|----------|--------|------|
| Base Input | 39 | $0.0006 |
| Cache Write (1h) | 110.9K | $3.33 |
| Cache Read | 535.0K | $0.80 |
| Output | 137 | $0.01 |
```

### Project overview

```
## Overview
| Field | Value |
|-------|-------|
| Total sessions | 117 |
| Total cost | $1,329.01 |
| Mean cost/session | $11.36 |
| Success rate | 72% |
```

## Data sources

Reads from Claude Code's local data stores (no API calls):

- `~/.claude/usage-data/session-meta/` — tokens, tools, duration, errors
- `~/.claude/usage-data/facets/` — outcomes, satisfaction, friction
- `~/.claude/projects/{encoded-path}/` — full transcripts with per-message token breakdown

## Plugin structure

```
analyze-session/
├── .claude-plugin/
│   └── plugin.json              # plugin manifest
├── skills/
│   └── analyze/
│       ├── SKILL.md             # skill definition
│       └── scripts/
│           ├── analyze.py       # analysis engine
│           ├── fix-report.py    # fix plan generator
│           └── run-analysis.sh  # standalone runner
├── hooks/
│   ├── hooks.json               # Stop hook (auto-analyze on session end)
│   └── hooks.json.example       # hook config reference
├── scripts/
│   └── export-plugin.sh         # zip exporter for distribution
├── tests/
│   ├── sample-report.md         # reference report
│   └── validate-report.py       # report validator
├── CLAUDE.md
├── CHANGELOG.md
└── README.md
```

## Testing

```bash
python3 tests/validate-report.py tests/sample-report.md
```

## License

MIT
