---
name: run
description: >
  Analyze Claude Code session performance, token usage, cost, tool efficiency,
  and quality metrics. Optionally fix issues from the report. Use whenever the
  user asks about session stats, token spending, cost breakdown, workflow
  efficiency, tool errors, or session optimization.
allowed-tools: ["Bash", "Read"]
argument-hint: "[session_id] [--scope session|project] [--project path] [--output path] [--fix [report_path]] [--apply]"
context: fork
agent: general-purpose
disable-model-invocation: true
---

# Analyze Session Skill

Unified skill for analyzing sessions and fixing issues from reports.

## Arguments

Parse `$ARGUMENTS` for these parameters:

| Param | Default | Description |
|-------|---------|-------------|
| `session_id` | `latest` | Session UUID or "latest" (analyze mode only) |
| `--project` | current working directory | Project path to analyze |
| `--scope` | `session` | `session` for single deep dive, `project` for cross-session trends |
| `--output` | `./SESSION-ANALYSIS.md` | Where to write the report |
| `--fix` | _(off)_ | Switch to fix mode. Optionally pass a report path (default: `./SESSION-ANALYSIS.md`) |
| `--apply` | _(off)_ | Auto-apply low-risk fixes (only with `--fix`) |

## Mode: Analyze (default)

1. Build the command from parsed arguments:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/analyze.py" \
  --session-id <session_id> \
  --project <project_path> \
  --scope <scope> \
  --output <output_path>
```

2. Run it with the Bash tool.

3. Read the output file with the Read tool.

4. Present a brief summary to the user highlighting:
   - **Total cost** and dominant model
   - **Biggest issue** found (if any)
   - **Top fix** recommendation (if any)
   - Key metrics (duration, tool calls, outcome)

5. If the script errors, show the error message and suggest:
   - Check that the project path is correct
   - Try specifying a session ID explicitly
   - Verify `~/.claude/usage-data/` has data

## Mode: Fix (`--fix`)

1. Build the command:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/fix-report.py" \
  --report <report_path> \
  --output ./fix-plan.md \
  [--apply]
```

2. Run it with the Bash tool.

3. Read `./fix-plan.md` with the Read tool.

4. Present the fix plan as your opening message. Guide discussion:
   - Prioritize top-impact fixes (cost savings first)
   - Propose exact changes (prompt diffs, skill YAML)
   - Estimate improvements
   - Ask before editing files

5. If `--apply` was used, also read the apply log and summarize what was auto-fixed.

## Notes

- The script uses only Python stdlib — no pip install needed.
- Cost calculations use per-message transcript data when available, falling back to session-meta aggregates.
- Cache token breakdown (5-min ephemeral, 1-hour ephemeral, cache reads) is extracted from transcripts for accurate cost attribution.
