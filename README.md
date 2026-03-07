# analyze-session

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugin that analyzes session performance, token costs, cache efficiency, tool usage, and quality metrics. Produces actionable Markdown reports from Claude Code's local data stores.

## What it does

- **Token & cost breakdown** with full cache detail (5-min ephemeral, 1-hour ephemeral, cache reads)
- **Tool usage** ranking with error tracking
- **Quality metrics** from Claude's self-assessed facets (outcome, helpfulness, friction)
- **Issue detection** with fix suggestions (high token turns, tool errors, cache cost, friction patterns)
- **Two scopes**: single-session deep dive or cross-session project trends
- **Fix companion**: reads the report and guides you through implementing fixes

## Install

Clone and load as a plugin:

```bash
git clone https://github.com/giovicordova/analyze-session.git
claude --plugin-dir ./analyze-session
```

No dependencies — uses Python stdlib only.

## Usage

In any Claude Code session:

```
/analyze-session:analyze-session
```

The report is saved as `SESSION-ANALYSIS.md` at the root of the project being analyzed.

To fix issues from the report:

```
/analyze-session:fix-session
```

### Options

| Param | Default | Description |
|-------|---------|-------------|
| `session_id` | `latest` | Session UUID or "latest" |
| `--project` | current directory | Project path to analyze |
| `--scope` | `session` | `session` for single session, `project` for all sessions |
| `--output` | `./SESSION-ANALYSIS.md` | Report output path |

### Examples

```
/analyze-session:analyze-session                              # latest session, current project
/analyze-session:analyze-session latest --scope project       # all sessions for current project
/analyze-session:analyze-session abc123-def --project ~/myapp # specific session, specific project
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

The skill reads from Claude Code's local data stores (no API calls):

- `~/.claude/usage-data/session-meta/` — tokens, tools, duration, errors
- `~/.claude/usage-data/facets/` — outcomes, satisfaction, friction
- `~/.claude/projects/{encoded-path}/` — full transcripts with per-message token breakdown

## License

MIT
