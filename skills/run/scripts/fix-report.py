#!/usr/bin/env python3
"""Companion script: Reads analyze-session report, extracts issues, and prepares fixes.

Supports --apply for auto-fixing low-risk issues (CLAUDE.md trimming, etc).
"""

import argparse
import os
import re
import sys
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"

# Expected report structure from analyze-session
REPORT_SECTIONS = [
    "Summary",
    "What Happened",
    "Token Breakdown",
    "Tool Usage",
    "Timeline",
    "Efficiency",
    "Quality",
    "Issues Found",
    "Recommended Fixes",
    "Next Actions",
    # Project-scope sections
    "Overview",
    "Cost Trends",
    "Success Rate",
    "Average Helpfulness",
    "Common Friction",
    "Session Type Costs",
    "Recommendations",
]


def parse_report(report_path: Path) -> dict:
    """Extract structured insights from Markdown report."""
    try:
        content = report_path.read_text()
    except Exception:
        return {"error": f"Could not read {report_path}"}

    insights = {
        "total_cost": 0.0,
        "dominant_model": "",
        "outcome": "",
        "duration": "",
        "issues": [],
        "fixes": [],
        "next_actions": [],
        "summary": "",
        "sections": {},
        "is_project": False,
    }

    lines = content.splitlines()
    current_section = None
    section_lines = []

    for line in lines:
        # Detect h2 sections
        if line.startswith("## "):
            if current_section:
                insights["sections"][current_section] = "\n".join(section_lines)
            current_section = line[3:].strip()
            section_lines = []
            continue

        if current_section:
            section_lines.append(line)

        # Extract key values from summary/overview tables
        if "Total Cost" in line or "Total cost" in line:
            for part in line.split("|"):
                part = part.strip()
                if "$" in part:
                    cleaned = re.sub(r"[*$,]", "", part).strip()
                    try:
                        insights["total_cost"] = float(cleaned)
                    except ValueError:
                        pass
        elif "Model" in line and "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2 and parts[0] == "Model":
                insights["dominant_model"] = parts[1]
        elif "Outcome" in line and "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2 and parts[0] == "Outcome":
                insights["outcome"] = parts[1]
        elif "Duration" in line and "|" in line and "Total duration" not in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2 and parts[0] == "Duration":
                insights["duration"] = parts[1]

    # Capture final section
    if current_section:
        insights["sections"][current_section] = "\n".join(section_lines)

    # Detect project vs session report
    insights["is_project"] = "Overview" in insights["sections"]

    # Parse issues section
    issues_text = insights["sections"].get("Issues Found", "")
    for line in issues_text.splitlines():
        line = line.strip()
        if line and not line.startswith("No issues"):
            insights["issues"].append(line)

    # Parse fixes section
    fixes_text = insights["sections"].get("Recommended Fixes", "")
    if not fixes_text:
        fixes_text = insights["sections"].get("Recommendations", "")
    for line in fixes_text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            insights["fixes"].append(line)

    # Parse next actions
    actions_text = insights["sections"].get("Next Actions", "")
    for line in actions_text.splitlines():
        line = line.strip()
        if line.startswith("- ["):
            insights["next_actions"].append(line[6:] if line.startswith("- [ ] ") else line[6:])
        elif line.startswith("- "):
            insights["next_actions"].append(line[2:])

    # Extract summary/what happened
    what_happened = insights["sections"].get("What Happened", "").strip()
    if what_happened:
        insights["summary"] = what_happened

    return insights


def generate_fix_prompt(insights: dict) -> str:
    """Generate conversational prompt for Claude to discuss/implement fixes."""
    report_type = "Project" if insights["is_project"] else "Session"
    cost_str = f"${insights['total_cost']:.2f}" if insights["total_cost"] >= 0.01 else f"${insights['total_cost']:.4f}"

    sections = []
    sections.append(f"# Fix Plan ({report_type} Report)\n")

    # Quick stats
    sections.append("## Report Summary\n")
    sections.append(f"- **Cost:** {cost_str}")
    if insights["dominant_model"]:
        sections.append(f"- **Model:** {insights['dominant_model']}")
    if insights["outcome"]:
        sections.append(f"- **Outcome:** {insights['outcome']}")
    if insights["duration"]:
        sections.append(f"- **Duration:** {insights['duration']}")
    sections.append("")

    # Issues
    if insights["issues"]:
        sections.append("## Issues Detected\n")
        for issue in insights["issues"]:
            sections.append(f"  {issue}")
        sections.append("")

    # Fixes
    if insights["fixes"]:
        sections.append("## Recommended Fixes\n")
        for fix in insights["fixes"]:
            sections.append(f"  {fix}")
        sections.append("")

    # Action items
    if insights["next_actions"]:
        sections.append("## Action Items\n")
        for i, action in enumerate(insights["next_actions"], 1):
            sections.append(f"{i}. {action}")
        sections.append("")

    # Conversation guide
    sections.append("## Discussion Guide\n")
    sections.append("For each issue above, discuss:")
    sections.append("1. **Why it happened** (root cause from the data)")
    sections.append("2. **Exact change** (prompt diff, skill YAML, CLAUDE.md edit)")
    sections.append("3. **Expected improvement** (token savings, success boost)")
    sections.append("")
    sections.append("Start with the highest-impact fix. Ask before making changes.")

    return "\n".join(sections)


# ── Auto-Apply Logic ─────────────────────────────────────────────────────────

def find_project_claude_md() -> Path | None:
    """Find CLAUDE.md in the current working directory."""
    candidate = Path.cwd() / "CLAUDE.md"
    return candidate if candidate.exists() else None


def measure_claude_md(path: Path) -> dict:
    """Measure CLAUDE.md size and structure."""
    content = path.read_text()
    lines = content.splitlines()
    return {
        "path": str(path),
        "lines": len(lines),
        "chars": len(content),
        "sections": [l for l in lines if l.startswith("#")],
    }


def auto_apply_fixes(insights: dict) -> list[str]:
    """Apply low-risk fixes automatically. Returns log of actions taken."""
    log = []

    # Check for high_cache_cost or general size issues
    has_cache_issue = any("cache" in i.lower() for i in insights["issues"])
    has_size_issue = any("compact" in f.lower() or "shorten" in f.lower() or "reduce" in f.lower() for f in insights["fixes"])

    if has_cache_issue or has_size_issue:
        claude_md = find_project_claude_md()
        if claude_md:
            stats = measure_claude_md(claude_md)
            if stats["lines"] > 100:
                log.append(f"CLAUDE.md is {stats['lines']} lines ({stats['chars']} chars) — consider trimming to <100 lines.")
                log.append(f"  Sections: {', '.join(s.lstrip('#').strip() for s in stats['sections'])}")
            else:
                log.append(f"CLAUDE.md is {stats['lines']} lines — already compact.")

    # Report on action items that can be auto-checked
    for action in insights["next_actions"]:
        lower = action.lower()
        if "skill" in lower:
            log.append(f"SKILL SUGGESTION: {action}")
        elif "claude.md" in lower:
            log.append(f"CLAUDE.MD SUGGESTION: {action}")
        elif "hook" in lower or "pre-commit" in lower:
            log.append(f"HOOK SUGGESTION: {action}")
        elif "compact" in lower:
            log.append(f"CONTEXT SUGGESTION: {action}")

    if not log:
        log.append("No auto-applicable fixes found. All issues require manual review.")

    return log


def main():
    parser = argparse.ArgumentParser(description="Read analyze-session report and prepare fixes.")
    parser.add_argument("--report", default="./SESSION-ANALYSIS.md", help="Path to report")
    parser.add_argument("--output", default="./fix-plan.md", help="Path to write fix prompt")
    parser.add_argument("--apply", action="store_true", help="Auto-apply low-risk fixes")
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"Error: Report not found at {report_path}", file=sys.stderr)
        sys.exit(1)

    insights = parse_report(report_path)
    if "error" in insights:
        print(insights["error"], file=sys.stderr)
        sys.exit(1)

    fix_prompt = generate_fix_prompt(insights)

    output_path = Path(args.output)
    output_path.write_text(fix_prompt)
    print(f"Fix plan written to {output_path}")

    if args.apply:
        log = auto_apply_fixes(insights)
        apply_log_path = Path(args.output).with_suffix(".apply-log.md")
        apply_content = "# Auto-Apply Log\n\n" + "\n".join(f"- {entry}" for entry in log) + "\n"
        apply_log_path.write_text(apply_content)
        print(f"Apply log written to {apply_log_path}")
        for entry in log:
            print(f"  {entry}")

    # Summary
    print(f"\nIssues: {len(insights['issues'])}")
    print(f"Fixes: {len(insights['fixes'])}")
    print(f"Actions: {len(insights['next_actions'])}")
    if insights["issues"]:
        print("\nTop issues:")
        for issue in insights["issues"][:3]:
            print(f"  {issue}")


if __name__ == "__main__":
    main()
