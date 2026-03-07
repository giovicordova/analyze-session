#!/usr/bin/env python3
"""Validate that an analyze-session report has correct structure and parseable data."""

import re
import sys
from pathlib import Path

REQUIRED_SESSION_SECTIONS = [
    "Summary",
    "Token Breakdown",
    "Tool Usage",
    "Issues Found",
    "Next Actions",
]

REQUIRED_PROJECT_SECTIONS = [
    "Overview",
    "Recommendations",
]

SUMMARY_FIELDS = [
    "Session ID",
    "Project",
    "Total Cost",
    "Outcome",
]

OVERVIEW_FIELDS = [
    "Project",
    "Total sessions",
    "Total cost",
]


def extract_sections(content: str) -> dict[str, str]:
    """Extract h2 sections from Markdown."""
    sections = {}
    current = None
    lines = []
    for line in content.splitlines():
        if line.startswith("## "):
            if current:
                sections[current] = "\n".join(lines)
            current = line[3:].strip()
            # Strip parenthetical suffixes like "Token Breakdown (Transcript)"
            current_base = current.split("(")[0].strip()
            sections[current_base] = ""
            current = current_base
            lines = []
        elif current:
            lines.append(line)
    if current:
        sections[current] = "\n".join(lines)
    return sections


def validate_table(section_text: str, required_fields: list[str]) -> list[str]:
    """Check that a table section contains expected fields."""
    errors = []
    for field in required_fields:
        if field not in section_text:
            errors.append(f"Missing field: '{field}'")
    return errors


def validate_cost_values(content: str) -> list[str]:
    """Check that cost values are parseable numbers."""
    errors = []
    cost_pattern = re.compile(r"\$[\d,]+\.?\d*")
    matches = cost_pattern.findall(content)
    if not matches:
        errors.append("No cost values found in report")
    for match in matches:
        try:
            float(match.replace("$", "").replace(",", ""))
        except ValueError:
            errors.append(f"Unparseable cost value: {match}")
    return errors


def validate_report(path: Path) -> tuple[bool, list[str]]:
    """Validate a report file. Returns (passed, errors)."""
    errors = []

    if not path.exists():
        return False, [f"File not found: {path}"]

    content = path.read_text()
    if not content.strip():
        return False, ["Report is empty"]

    # Must start with h1
    if not content.startswith("# "):
        errors.append("Report must start with an h1 heading")

    sections = extract_sections(content)
    is_project = "Overview" in sections

    # Check required sections
    required = REQUIRED_PROJECT_SECTIONS if is_project else REQUIRED_SESSION_SECTIONS
    for section in required:
        if section not in sections:
            errors.append(f"Missing required section: '{section}'")

    # Validate summary/overview table
    if is_project and "Overview" in sections:
        errors.extend(validate_table(sections["Overview"], OVERVIEW_FIELDS))
    elif "Summary" in sections:
        errors.extend(validate_table(sections["Summary"], SUMMARY_FIELDS))

    # Validate cost values
    errors.extend(validate_cost_values(content))

    # Check that Issues Found exists and isn't just empty
    issues_section = sections.get("Issues Found", "")
    if not issues_section.strip():
        errors.append("Issues Found section is empty (should say 'No issues detected' if clean)")

    return len(errors) == 0, errors


def main():
    if len(sys.argv) < 2:
        # Default: validate the sample report
        report_path = Path(__file__).parent / "sample-report.md"
    else:
        report_path = Path(sys.argv[1])

    print(f"Validating: {report_path}")
    passed, errors = validate_report(report_path)

    if passed:
        print("PASS — Report structure is valid.")
    else:
        print(f"FAIL — {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
