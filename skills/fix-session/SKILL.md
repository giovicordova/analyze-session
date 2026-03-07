---
name: fix-session
description: Reads latest analyze-session report, extracts issues/fixes, and starts chat on implementing them.
allowed-tools: ["Bash", "Read"]
---

Parse $ARGUMENTS for --report (default: ./SESSION-ANALYSIS.md)

Run: python3 "${CLAUDE_SKILL_DIR}/scripts/fix-report.py" --report <path> --output ./fix-plan.md

Read ./fix-plan.md and paste it into chat as your opening message. Guide discussion:
- Prioritize top-impact fixes (cost savings first)
- Propose exact changes (prompt diffs, skill YAML)
- Estimate improvements
- Ask before editing files

Example: "Report shows high MCP errors—want to add retry logic to the skill?"
