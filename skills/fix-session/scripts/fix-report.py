#!/usr/bin/env python3
"""Companion skill: Reads analyze-session report and prepares fixes."""

import argparse
import os
import sys
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"

# Expected report structure from analyze-session
REPORT_SECTIONS = [
    "Summary",
    "Token Breakdown",
    "Tool Usage",
    "Efficiency",
    "Issues Found",
    "Recommended Fixes",
    "Next Actions",
]

# Fix templates by issue type
def get_fix_prompt(issue_type: str, details: str) -> str:
    templates = {
        "high_tokens": "High token usage detected. Suggest prompt shortening or context reduction. Details: {details}",
        "tool_errors": "Tool failures found. Propose error handling, permissions, or alternatives. Details: {details}",
        "low_satisfaction": "Low helpfulness score. Recommend clearer goals or validation steps. Details: {details}",
        "friction": "Friction points identified. Create targeted skills or CLAUDE.md updates. Details: {details}",
        "high_cache_cost": "Cache inefficiency. Advise /compact usage or instruction trimming. Details: {details}",
    }
    return templates.get(issue_type, f"Address this issue: {{details}}").format(details=details)


def parse_report(report_path: Path) -> dict:
    """Extract key insights and fixes from Markdown report."""
    try:
        content = report_path.read_text()
    except:
        return {"error": f"Could not read {report_path}"}

    insights = {
        "total_cost": 0.0,
        "issues": [],
        "fixes": [],
        "next_actions": [],
        "summary": "",
    }

    lines = content.splitlines()
    in_issues = False
    in_fixes = False
    in_actions = False

    for line in lines:
        if "Total cost" in line or "cost:" in line.lower():
            # Extract cost number
            for part in line.split():
                if '$' in part:
                    try:
                        insights["total_cost"] = float(part.replace('$', '').replace(',', ''))
                    except:
                        pass
        elif line.strip().startswith("## Issues Found"):
            in_issues = True
        elif line.strip().startswith("## Recommended Fixes"):
            in_issues = False
            in_fixes = True
        elif line.strip().startswith("## Next Actions"):
            in_fixes = False
            in_actions = True
        elif in_issues and line.strip() and not line.startswith("##"):
            insights["issues"].append(line.strip())
        elif in_fixes and line.strip() and not line.startswith("##"):
            insights["fixes"].append(line.strip())
        elif in_actions and line.strip() and line.startswith("- "):
            insights["next_actions"].append(line.strip()[2:])

    return insights


def generate_fix_prompt(insights: dict) -> str:
    """Generate conversational prompt for Claude to discuss/implement fixes."""
    prompt = f"""
You are the Analyze-Fix companion. I just ran /analyze-session and got this report summary:

Cost: ${insights.get('total_cost', 0):.4f}

Issues:
{chr(10).join(f'- {i}' for i in insights.get('issues', []))}

Recommended Fixes:
{chr(10).join(f'- {f}' for f in insights.get('fixes', []))}

Next Actions:
{chr(10).join(f'- {a}' for a in insights.get('next_actions', []))}

Now, let's chat about implementing these. For each issue, explain:
1. Why it happened (based on details)
2. Exact change to make (prompt/skill/CLAUDE.md diff if possible)
3. Expected improvement (tokens saved, success boost)

Start with the highest-impact fix. Ask me before making changes.
    """
    return prompt.strip()


def main():
    parser = argparse.ArgumentParser(description="Read analyze-session report and prepare fixes.")
    parser.add_argument("--report", default="./SESSION-ANALYSIS.md", help="Path to report")
    parser.add_argument("--output", default="./fix-plan.md", help="Path to write fix prompt")
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"Error: Report not found at {report_path}")
        sys.exit(1)

    insights = parse_report(report_path)
    if "error" in insights:
        print(insights["error"])
        sys.exit(1)

    fix_prompt = generate_fix_prompt(insights)

    output_path = Path(args.output)
    output_path.write_text(fix_prompt)

    print(f"Fix prompt written to {output_path}")
    print("\nTop issues detected:")
    for issue in insights.get('issues', [])[:3]:
        print(f"  - {issue}")

if __name__ == "__main__":
    main()