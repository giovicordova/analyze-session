---
name: analyze-session
description: >
  Analyze Claude Code session performance, token usage, cost, tool efficiency,
  and quality metrics. Use whenever the user asks about session stats, token
  spending, cost breakdown, workflow efficiency, tool errors, or session
  optimization — even if they don't say "analyze session" explicitly.
allowed-tools: ["Bash", "Read"]
argument-hint: "[session_id] [--scope session|project] [--project path] [--output path]"
context: fork
agent: general-purpose
---

# Analyze Session Skill

Runs the bundled Python analysis script and presents results.

## Arguments

Parse `$ARGUMENTS` for these parameters:

| Param | Default | Description |
|-------|---------|-------------|
| `session_id` | `latest` | Session UUID or "latest" |
| `--project` | current working directory | Project path to analyze |
| `--scope` | `session` | `session` for single deep dive, `project` for cross-session trends |
| `--output` | `./SESSION-ANALYSIS.md` | Where to write the report |

## Execution

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

## Notes

- The script uses only Python stdlib — no pip install needed.
- Cost calculations use per-message transcript data when available, falling back to session-meta aggregates.
- Cache token breakdown (5-min ephemeral, 1-hour ephemeral, cache reads) is extracted from transcripts for accurate cost attribution.
