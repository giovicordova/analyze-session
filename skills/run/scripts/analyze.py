#!/usr/bin/env python3
"""Analyze Claude Code session performance, token usage, cost, and quality metrics.

Reads directly from ~/.claude/projects/ JSONL transcripts — the live data source
that Claude Code continuously writes to. Does NOT depend on the stale
usage-data/session-meta/ snapshot.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Section A: Data Loading ──────────────────────────────────────────────────

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
FACETS_DIR = CLAUDE_DIR / "usage-data" / "facets"

# Cost per million tokens by model family
PRICING = {
    "opus": {
        "input": 15.0,
        "cache_write_5m": 18.75,
        "cache_write_1h": 30.0,
        "cache_read": 1.50,
        "output": 75.0,
    },
    "sonnet": {
        "input": 3.0,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.0,
        "cache_read": 0.30,
        "output": 15.0,
    },
    "haiku": {
        "input": 1.0,
        "cache_write_5m": 1.25,
        "cache_write_1h": 2.0,
        "cache_read": 0.10,
        "output": 5.0,
    },
}


def encode_project_path(path: str) -> str:
    """Encode a filesystem path to Claude Code's directory format.

    Replaces '/' with '-', producing the directory name used
    under ~/.claude/projects/.
    """
    encoded = path.replace("/", "-")
    if not encoded.startswith("-"):
        encoded = "-" + encoded
    return encoded


def model_family(model_str: str) -> str:
    """Map a model ID like 'claude-opus-4-6' to a pricing family key."""
    m = model_str.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return "opus"  # default to most expensive for safety


def load_json(path: Path):
    """Load a JSON file, return None on any error."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _read_jsonl(path: Path) -> list[dict]:
    lines = []
    try:
        with open(path) as f:
            for raw in f:
                raw = raw.strip()
                if raw:
                    try:
                        lines.append(json.loads(raw))
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    return lines


def find_project_dir(project_path: str) -> Path | None:
    """Find the ~/.claude/projects/ directory for a given project path."""
    encoded = encode_project_path(os.path.normpath(project_path))
    proj_dir = PROJECTS_DIR / encoded
    if proj_dir.is_dir():
        return proj_dir
    # Try with underscores replaced too (legacy encoding)
    encoded_legacy = project_path.replace("/", "-").replace("_", "-")
    if not encoded_legacy.startswith("-"):
        encoded_legacy = "-" + encoded_legacy
    proj_dir_legacy = PROJECTS_DIR / encoded_legacy
    if proj_dir_legacy.is_dir():
        return proj_dir_legacy
    return None


def list_session_ids(proj_dir: Path) -> list[str]:
    """List all session IDs that have JSONL transcripts in a project dir."""
    ids = set()
    for f in proj_dir.glob("*.jsonl"):
        ids.add(f.stem)
    return sorted(ids)


def load_transcript(session_id: str, proj_dir: Path) -> list[dict]:
    """Load transcript JSONL for a session from its project directory."""
    messages = []

    # Flat file
    jsonl = proj_dir / f"{session_id}.jsonl"
    if jsonl.exists():
        messages = _read_jsonl(jsonl)

    # Directory format (subagent sessions)
    session_dir = proj_dir / session_id
    if session_dir.is_dir():
        for sub in sorted(session_dir.glob("**/*.jsonl")):
            messages.extend(_read_jsonl(sub))

    return messages


def load_facet(session_id: str) -> dict | None:
    return load_json(FACETS_DIR / f"{session_id}.json")


def extract_session_info(transcript: list[dict]) -> dict:
    """Extract metadata from a transcript's entries (timestamps, counts, tools)."""
    first_ts = None
    last_ts = None
    user_count = 0
    assistant_count = 0
    tool_uses = {}
    tool_errors = 0
    session_id = None
    cwd = None

    for entry in transcript:
        ts = entry.get("timestamp")
        if ts:
            if not first_ts:
                first_ts = ts
            last_ts = ts

        if not session_id:
            session_id = entry.get("sessionId")
        if not cwd:
            cwd = entry.get("cwd")

        etype = entry.get("type")
        if etype == "human":
            user_count += 1
        elif etype == "assistant":
            assistant_count += 1
            content = entry.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name", "unknown")
                        tool_uses[tool_name] = tool_uses.get(tool_name, 0) + 1
        elif etype == "tool_result":
            data = entry.get("data", {})
            if isinstance(data, dict) and data.get("is_error"):
                tool_errors += 1

    duration_minutes = 0
    if first_ts and last_ts:
        try:
            t1 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            duration_minutes = round((t2 - t1).total_seconds() / 60, 1)
        except Exception:
            pass

    return {
        "session_id": session_id,
        "start_time": first_ts,
        "end_time": last_ts,
        "duration_minutes": duration_minutes,
        "user_message_count": user_count,
        "assistant_message_count": assistant_count,
        "tool_counts": dict(sorted(tool_uses.items(), key=lambda x: -x[1])),
        "tool_errors": tool_errors,
        "cwd": cwd,
    }


def find_latest_session(proj_dir: Path) -> tuple[str, list[dict]] | None:
    """Find the most recent session by checking last-modified time of JSONL files."""
    jsonl_files = list(proj_dir.glob("*.jsonl"))
    if not jsonl_files:
        return None
    # Sort by modification time, newest first
    jsonl_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    session_id = jsonl_files[0].stem
    transcript = load_transcript(session_id, proj_dir)
    if not transcript:
        return None
    return session_id, transcript


# ── Section B: Single Session Analysis ───────────────────────────────────────

def cost_per_m(tokens: int, rate: float) -> float:
    return tokens * rate / 1_000_000


def analyze_transcript_tokens(transcript: list[dict]) -> dict:
    """Parse assistant messages from transcript to get detailed token/cost breakdown."""
    totals = {
        "input_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cache_read_tokens": 0,
        "output_tokens": 0,
        "models": {},
        "high_output_turns": [],
        "assistant_message_count": 0,
    }

    for entry in transcript:
        if entry.get("type") != "assistant":
            continue
        msg = entry.get("message", {})
        usage = msg.get("usage", {})
        if not usage:
            continue

        totals["assistant_message_count"] += 1
        model = msg.get("model", "unknown")
        totals["models"][model] = totals["models"].get(model, 0) + 1

        inp = usage.get("input_tokens", 0)
        cache_creation = usage.get("cache_creation", {})
        cw5 = cache_creation.get("ephemeral_5m_input_tokens", 0)
        cw1h = cache_creation.get("ephemeral_1h_input_tokens", 0)
        # Also check top-level cache_creation_input_tokens as fallback
        if not cw5 and not cw1h:
            cw1h = usage.get("cache_creation_input_tokens", 0)
        cr = usage.get("cache_read_input_tokens", 0)
        out = usage.get("output_tokens", 0)

        totals["input_tokens"] += inp
        totals["cache_write_5m_tokens"] += cw5
        totals["cache_write_1h_tokens"] += cw1h
        totals["cache_read_tokens"] += cr
        totals["output_tokens"] += out

        if out > 10000:
            totals["high_output_turns"].append({
                "model": model,
                "output_tokens": out,
                "uuid": entry.get("uuid", "?"),
            })

    return totals


def compute_costs(token_totals: dict) -> dict:
    """Compute dollar costs from token totals. Uses the dominant model's pricing."""
    models = token_totals.get("models", {})
    if models:
        dominant = max(models, key=models.get)
        family = model_family(dominant)
    else:
        family = "opus"

    rates = PRICING[family]
    costs = {
        "input": cost_per_m(token_totals["input_tokens"], rates["input"]),
        "cache_write_5m": cost_per_m(token_totals["cache_write_5m_tokens"], rates["cache_write_5m"]),
        "cache_write_1h": cost_per_m(token_totals["cache_write_1h_tokens"], rates["cache_write_1h"]),
        "cache_read": cost_per_m(token_totals["cache_read_tokens"], rates["cache_read"]),
        "output": cost_per_m(token_totals["output_tokens"], rates["output"]),
        "model_family": family,
        "dominant_model": max(models, key=models.get) if models else "unknown",
    }
    costs["total"] = sum(v for k, v in costs.items() if isinstance(v, float))
    return costs


def detect_issues(token_totals: dict, costs: dict, info: dict, facet: dict | None) -> list[dict]:
    """Detect session issues and generate fix suggestions."""
    issues = []

    # High-output turns
    for turn in token_totals.get("high_output_turns", []):
        issues.append({
            "type": "high_tokens",
            "detail": f"Turn produced {turn['output_tokens']:,} output tokens (model: {turn['model']})",
            "fix": "Break into smaller sessions or add skills to reduce repeated context.",
        })

    # Tool errors
    errors = info.get("tool_errors", 0)
    if errors > 0:
        issues.append({
            "type": "tool_errors",
            "detail": f"{errors} tool error(s)",
            "fix": "Review error patterns, add permission rules or fix tool configuration.",
        })

    # Low satisfaction (from facets if available)
    if facet:
        helpfulness = facet.get("claude_helpfulness", "")
        if helpfulness and helpfulness not in ("essential", "very_helpful"):
            issues.append({
                "type": "low_satisfaction",
                "detail": f"Session helpfulness rated '{helpfulness}'",
                "fix": "Session had low effectiveness — review for scope or communication issues.",
            })

        friction = facet.get("friction_counts", {})
        for ftype, count in friction.items():
            detail_text = facet.get("friction_detail", "")
            fix_map = {
                "wrong_approach": "Add specific guidance to CLAUDE.md or create a skill.",
                "buggy_code": "Add test hooks or pre-commit validation.",
                "slow_response": "Use /compact, reduce context, or switch to a faster model.",
                "hallucination": "Add verification steps or reference documentation.",
            }
            issues.append({
                "type": "friction",
                "detail": f"Friction: {ftype} x{count}" + (f" — {detail_text}" if detail_text else ""),
                "fix": fix_map.get(ftype, "Review session for recurring friction patterns."),
            })

    # High cache write cost
    total_cost = costs.get("total", 0)
    cache_cost = costs.get("cache_write_5m", 0) + costs.get("cache_write_1h", 0)
    if total_cost > 0 and cache_cost / total_cost > 0.6:
        pct = cache_cost / total_cost * 100
        issues.append({
            "type": "high_cache_cost",
            "detail": f"Cache writes are {pct:.0f}% of total cost (${cache_cost:.4f} of ${total_cost:.4f})",
            "fix": "Use /compact, shorten system instructions, or reduce CLAUDE.md size.",
        })

    return issues


def analyze_single_session(session_id: str, proj_dir: Path, project_path: str) -> dict:
    """Full analysis of a single session from its JSONL transcript."""
    transcript = load_transcript(session_id, proj_dir)
    if not transcript:
        return {"error": f"No transcript found for session {session_id}"}

    info = extract_session_info(transcript)
    facet = load_facet(session_id)
    token_totals = analyze_transcript_tokens(transcript)
    costs = compute_costs(token_totals)
    issues = detect_issues(token_totals, costs, info, facet)

    return {
        "session_id": session_id,
        "project_path": project_path,
        "info": info,
        "facet": facet,
        "token_totals": token_totals,
        "costs": costs,
        "issues": issues,
    }


# ── Section C: Cross-Session Analysis ───────────────────────────────────────

HELPFULNESS_SCORES = {
    "essential": 5,
    "very_helpful": 4,
    "helpful": 3,
    "slightly_helpful": 2,
    "not_helpful": 1,
}


def analyze_project(project_path: str) -> dict:
    """Aggregate analysis across all sessions for a project."""
    proj_dir = find_project_dir(project_path)
    if not proj_dir:
        return {"error": f"No project data found for: {project_path}"}

    session_ids = list_session_ids(proj_dir)
    if not session_ids:
        return {"error": f"No sessions found for project: {project_path}"}

    all_analyses = []
    total_cost = 0.0
    total_input = 0
    total_output = 0
    tool_usage = {}
    tool_errors_total = 0
    outcomes = {}
    helpfulness_scores = []
    friction_types = {}
    durations = []

    for sid in session_ids:
        analysis = analyze_single_session(sid, proj_dir, project_path)
        if "error" in analysis:
            continue
        all_analyses.append(analysis)

        cost = analysis["costs"]["total"]
        total_cost += cost
        total_input += analysis["token_totals"]["input_tokens"]
        total_output += analysis["token_totals"]["output_tokens"]

        info = analysis["info"]
        dur = info.get("duration_minutes", 0)
        if dur:
            durations.append(dur)

        for tool, count in info.get("tool_counts", {}).items():
            tool_usage[tool] = tool_usage.get(tool, 0) + count

        tool_errors_total += info.get("tool_errors", 0)

        facet = analysis.get("facet")
        if facet:
            outcome = facet.get("outcome", "unknown")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1

            h = facet.get("claude_helpfulness", "")
            if h in HELPFULNESS_SCORES:
                helpfulness_scores.append(HELPFULNESS_SCORES[h])

            for ftype, count in facet.get("friction_counts", {}).items():
                friction_types[ftype] = friction_types.get(ftype, 0) + count

    n = len(all_analyses)
    if n == 0:
        return {"error": f"No analyzable sessions for project: {project_path}"}

    costs_list = [a["costs"]["total"] for a in all_analyses]

    # Sort analyses by start time for trend calculation
    all_analyses.sort(key=lambda a: a["info"].get("start_time") or "")

    half = n // 2
    first_half = all_analyses[:half] if half > 0 else []
    second_half = all_analyses[half:] if half > 0 else all_analyses

    def avg_cost(group):
        if not group:
            return 0.0
        return sum(a["costs"]["total"] for a in group) / len(group)

    sorted_costs = sorted(costs_list)
    median_cost = sorted_costs[len(sorted_costs) // 2] if sorted_costs else 0.0

    first_time = all_analyses[0]["info"].get("start_time", "?") if all_analyses else "?"
    last_time = all_analyses[-1]["info"].get("start_time", "?") if all_analyses else "?"

    return {
        "project_path": project_path,
        "session_count": n,
        "time_span": {
            "first": first_time,
            "last": last_time,
        },
        "total_cost": total_cost,
        "mean_cost": total_cost / n if n else 0,
        "median_cost": median_cost,
        "max_cost": max(costs_list) if costs_list else 0,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_duration_minutes": sum(durations),
        "tool_usage": dict(sorted(tool_usage.items(), key=lambda x: -x[1])),
        "tool_errors": tool_errors_total,
        "outcomes": outcomes,
        "avg_helpfulness": sum(helpfulness_scores) / len(helpfulness_scores) if helpfulness_scores else None,
        "friction_types": dict(sorted(friction_types.items(), key=lambda x: -x[1])),
        "trend": {
            "first_half_avg_cost": avg_cost(first_half),
            "second_half_avg_cost": avg_cost(second_half),
            "first_half_count": len(first_half),
            "second_half_count": len(second_half),
        },
        "sessions": all_analyses,
    }


# ── Section D: Report Generation & CLI ───────────────────────────────────────

def fmt_cost(val: float) -> str:
    if val < 0.01:
        return f"${val:.4f}"
    return f"${val:.2f}"


def fmt_tokens(val: int) -> str:
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"{val / 1_000:.1f}K"
    return str(val)


def render_session_report(analysis: dict) -> str:
    """Generate Markdown report for a single session."""
    if "error" in analysis:
        return f"# Session Analysis Error\n\n{analysis['error']}\n"

    info = analysis["info"]
    facet = analysis.get("facet")
    tt = analysis["token_totals"]
    costs = analysis["costs"]
    issues = analysis["issues"]

    lines = ["# Session Analysis Report\n"]

    # Summary table
    outcome = facet.get("outcome", "—") if facet else "—"
    lines.append("## Summary\n")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Session ID | `{analysis['session_id']}` |")
    lines.append(f"| Project | `{analysis['project_path']}` |")
    lines.append(f"| Started | {info.get('start_time', '?')} |")
    lines.append(f"| Duration | {info.get('duration_minutes', '?')} min |")
    lines.append(f"| Model | {costs['dominant_model']} |")
    lines.append(f"| Total Cost | **{fmt_cost(costs['total'])}** |")
    lines.append(f"| Outcome | {outcome} |")
    lines.append("")

    # What happened
    if facet and facet.get("brief_summary"):
        lines.append("## What Happened\n")
        lines.append(facet["brief_summary"])
        lines.append("")

    # Token breakdown
    lines.append("## Token Breakdown\n")
    lines.append("| Category | Tokens | Cost |")
    lines.append("|----------|--------|------|")
    lines.append(f"| Base Input | {fmt_tokens(tt['input_tokens'])} | {fmt_cost(costs['input'])} |")
    lines.append(f"| Cache Write (5m) | {fmt_tokens(tt['cache_write_5m_tokens'])} | {fmt_cost(costs['cache_write_5m'])} |")
    lines.append(f"| Cache Write (1h) | {fmt_tokens(tt['cache_write_1h_tokens'])} | {fmt_cost(costs['cache_write_1h'])} |")
    lines.append(f"| Cache Read | {fmt_tokens(tt['cache_read_tokens'])} | {fmt_cost(costs['cache_read'])} |")
    lines.append(f"| Output | {fmt_tokens(tt['output_tokens'])} | {fmt_cost(costs['output'])} |")
    lines.append(f"| **Total** | | **{fmt_cost(costs['total'])}** |")
    lines.append("")

    # Tool usage
    tool_counts = info.get("tool_counts", {})
    if tool_counts:
        lines.append("## Tool Usage\n")
        lines.append("| Tool | Calls |")
        lines.append("|------|-------|")
        for tool, count in tool_counts.items():
            lines.append(f"| {tool} | {count} |")
        if info.get("tool_errors", 0) > 0:
            lines.append(f"\n**Tool errors:** {info['tool_errors']}")
        lines.append("")

    # Timeline
    lines.append("## Timeline\n")
    dur = info.get("duration_minutes", 0)
    user_msgs = info.get("user_message_count", 0)
    asst_msgs = info.get("assistant_message_count", 0)
    total_tools = sum(tool_counts.values()) if tool_counts else 0
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Duration | {dur} min |")
    lines.append(f"| User messages | {user_msgs} |")
    lines.append(f"| Assistant messages | {asst_msgs} |")
    lines.append(f"| Total tool calls | {total_tools} |")
    if dur > 0:
        lines.append(f"| Messages/min | {(user_msgs + asst_msgs) / dur:.1f} |")
        lines.append(f"| Tools/min | {total_tools / dur:.1f} |")
    lines.append("")

    # Quality (from facets)
    if facet:
        lines.append("## Quality\n")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Outcome | {facet.get('outcome', '—')} |")
        lines.append(f"| Helpfulness | {facet.get('claude_helpfulness', '—')} |")
        lines.append(f"| Session type | {facet.get('session_type', '—')} |")
        lines.append(f"| Primary success | {facet.get('primary_success', '—')} |")
        if facet.get("friction_counts"):
            lines.append(f"| Friction | {', '.join(f'{k}: {v}' for k, v in facet['friction_counts'].items())} |")
        lines.append("")
    else:
        lines.append("## Quality\n")
        lines.append("No quality data available (facet file missing).\n")

    # Issues
    if issues:
        lines.append("## Issues Found\n")
        for i, issue in enumerate(issues, 1):
            lines.append(f"{i}. **{issue['type']}** — {issue['detail']}")
        lines.append("")

        lines.append("## Recommended Fixes\n")
        seen = set()
        for issue in issues:
            key = issue["fix"]
            if key not in seen:
                seen.add(key)
                lines.append(f"### {issue['type'].replace('_', ' ').title()}\n")
                lines.append(f"**Problem:** {issue['detail']}\n")
                lines.append(f"**Fix:** {issue['fix']}\n")
    else:
        lines.append("## Issues Found\n")
        lines.append("No issues detected.\n")

    # Next actions
    lines.append("## Next Actions\n")
    if issues:
        for issue in issues:
            lines.append(f"- [ ] {issue['fix']}")
    else:
        lines.append("- [x] Session looks healthy — no action needed")
    lines.append("")

    return "\n".join(lines)


def render_project_report(analysis: dict) -> str:
    """Generate Markdown report for cross-session project analysis."""
    if "error" in analysis:
        return f"# Project Analysis Error\n\n{analysis['error']}\n"

    lines = ["# Project Analysis Report\n"]

    # Overview
    first_ts = analysis["time_span"]["first"] or "?"
    last_ts = analysis["time_span"]["last"] or "?"
    lines.append("## Overview\n")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Project | `{analysis['project_path']}` |")
    lines.append(f"| Total sessions | {analysis['session_count']} |")
    lines.append(f"| Time span | {first_ts[:10]} to {last_ts[:10]} |")
    lines.append(f"| Total duration | {analysis['total_duration_minutes']} min |")
    lines.append(f"| Total cost | **{fmt_cost(analysis['total_cost'])}** |")
    lines.append(f"| Mean cost/session | {fmt_cost(analysis['mean_cost'])} |")
    lines.append(f"| Median cost/session | {fmt_cost(analysis['median_cost'])} |")
    lines.append(f"| Max cost session | {fmt_cost(analysis['max_cost'])} |")
    lines.append(f"| Total input tokens | {fmt_tokens(analysis['total_input_tokens'])} |")
    lines.append(f"| Total output tokens | {fmt_tokens(analysis['total_output_tokens'])} |")
    lines.append("")

    # Cost trends
    trend = analysis["trend"]
    if trend["first_half_count"] > 0:
        lines.append("## Cost Trends\n")
        lines.append("| Period | Sessions | Avg Cost |")
        lines.append("|--------|----------|----------|")
        lines.append(f"| First half | {trend['first_half_count']} | {fmt_cost(trend['first_half_avg_cost'])} |")
        lines.append(f"| Second half | {trend['second_half_count']} | {fmt_cost(trend['second_half_avg_cost'])} |")
        if trend["first_half_avg_cost"] > 0:
            diff = trend["second_half_avg_cost"] - trend["first_half_avg_cost"]
            pct = diff / trend["first_half_avg_cost"] * 100
            direction = "up" if pct > 0 else "down"
            lines.append(f"\nTrend: {direction} {abs(pct):.0f}% from first to second half.\n")
        lines.append("")

    # Tool usage
    if analysis["tool_usage"]:
        lines.append("## Tool Usage (All Sessions)\n")
        lines.append("| Tool | Total Calls |")
        lines.append("|------|-------------|")
        for tool, count in list(analysis["tool_usage"].items())[:20]:
            lines.append(f"| {tool} | {count} |")
        lines.append("")

    if analysis["tool_errors"] > 0:
        lines.append(f"**Total tool errors across all sessions:** {analysis['tool_errors']}\n")

    # Success rate
    if analysis["outcomes"]:
        lines.append("## Success Rate\n")
        lines.append("| Outcome | Count |")
        lines.append("|---------|-------|")
        for outcome, count in sorted(analysis["outcomes"].items(), key=lambda x: -x[1]):
            lines.append(f"| {outcome} | {count} |")
        total_outcomes = sum(analysis["outcomes"].values())
        success = analysis["outcomes"].get("fully_achieved", 0) + analysis["outcomes"].get("mostly_achieved", 0)
        if total_outcomes > 0:
            lines.append(f"\nSuccess rate: **{success / total_outcomes * 100:.0f}%** ({success}/{total_outcomes})\n")
        lines.append("")

    # Helpfulness
    if analysis["avg_helpfulness"] is not None:
        lines.append("## Average Helpfulness\n")
        score = analysis["avg_helpfulness"]
        label = "essential" if score >= 4.5 else "very helpful" if score >= 3.5 else "helpful" if score >= 2.5 else "low"
        lines.append(f"Score: **{score:.1f}/5** ({label})\n")

    # Friction
    if analysis["friction_types"]:
        lines.append("## Common Friction\n")
        lines.append("| Type | Count |")
        lines.append("|------|-------|")
        for ftype, count in analysis["friction_types"].items():
            lines.append(f"| {ftype} | {count} |")
        lines.append("")

    # Recommendations
    lines.append("## Recommendations\n")
    recs = []
    if analysis["friction_types"]:
        top_friction = list(analysis["friction_types"].keys())[0]
        fix_map = {
            "wrong_approach": "Add guidance to CLAUDE.md or create targeted skills.",
            "buggy_code": "Add test hooks or pre-commit validation.",
            "slow_response": "Use /compact or reduce context size.",
            "hallucination": "Add verification steps and reference docs.",
        }
        recs.append(f"- Top friction: **{top_friction}** — {fix_map.get(top_friction, 'Review for patterns.')}")

    trend = analysis["trend"]
    if trend["first_half_avg_cost"] > 0 and trend["second_half_avg_cost"] > trend["first_half_avg_cost"] * 1.2:
        recs.append("- Cost is trending up — review recent sessions for inefficiency.")

    if analysis["avg_helpfulness"] is not None and analysis["avg_helpfulness"] < 3.5:
        recs.append("- Average helpfulness below 'very helpful' — review task scoping and communication.")

    if not recs:
        recs.append("- Project metrics look healthy. No action needed.")

    lines.extend(recs)
    lines.append("")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Analyze Claude Code session performance")
    parser.add_argument("--session-id", default="latest", help="Session UUID or 'latest'")
    parser.add_argument("--project", default=os.getcwd(), help="Project path (default: cwd)")
    parser.add_argument("--scope", choices=["session", "project"], default="session")
    parser.add_argument("--output", default="./SESSION-ANALYSIS.md", help="Output file path")
    args = parser.parse_args()

    project_path = os.path.normpath(args.project)

    proj_dir = find_project_dir(project_path)
    if not proj_dir:
        print(f"Error: No project data found at: {project_path}", file=sys.stderr)
        print(f"Looked for: {PROJECTS_DIR / encode_project_path(project_path)}", file=sys.stderr)
        print("Make sure you've run at least one Claude Code session in this project.", file=sys.stderr)
        sys.exit(1)

    if args.scope == "project":
        analysis = analyze_project(project_path)
        report = render_project_report(analysis)
    else:
        if args.session_id == "latest":
            result = find_latest_session(proj_dir)
            if not result:
                print(f"Error: No session transcripts found for project: {project_path}", file=sys.stderr)
                sys.exit(1)
            session_id, _ = result
        else:
            session_id = args.session_id

        analysis = analyze_single_session(session_id, proj_dir, project_path)
        report = render_session_report(analysis)

    # Write report
    output_path = os.path.expanduser(args.output)
    with open(output_path, "w") as f:
        f.write(report)

    print(f"Report written to: {output_path}")

    if "error" in analysis:
        print(f"Error: {analysis['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
