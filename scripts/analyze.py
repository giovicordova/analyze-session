#!/usr/bin/env python3
"""Analyze Claude Code session performance, token usage, cost, and quality metrics."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Section A: Data Loading ──────────────────────────────────────────────────

CLAUDE_DIR = Path.home() / ".claude"
SESSION_META_DIR = CLAUDE_DIR / "usage-data" / "session-meta"
FACETS_DIR = CLAUDE_DIR / "usage-data" / "facets"
PROJECTS_DIR = CLAUDE_DIR / "projects"

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

    Replaces '/' and '_' with '-', producing the directory name used
    under ~/.claude/projects/.
    """
    encoded = path.replace("/", "-").replace("_", "-")
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


def load_all_session_metas() -> list[dict]:
    """Load every session-meta JSON into a list."""
    metas = []
    if not SESSION_META_DIR.exists():
        return metas
    for f in SESSION_META_DIR.glob("*.json"):
        d = load_json(f)
        if d:
            metas.append(d)
    return metas


def find_all_project_sessions(project_path: str) -> list[dict]:
    """Return all session-meta dicts whose project_path matches."""
    norm = os.path.normpath(project_path)
    return sorted(
        [m for m in load_all_session_metas() if os.path.normpath(m.get("project_path", "")) == norm],
        key=lambda m: m.get("start_time", ""),
    )


def find_latest_session(project_path: str) -> dict | None:
    """Find the most recent session-meta for a given project."""
    sessions = find_all_project_sessions(project_path)
    return sessions[-1] if sessions else None


def load_session_meta(session_id: str) -> dict | None:
    return load_json(SESSION_META_DIR / f"{session_id}.json")


def load_facet(session_id: str) -> dict | None:
    return load_json(FACETS_DIR / f"{session_id}.json")


def load_transcript(session_id: str, project_path: str) -> list[dict]:
    """Load transcript JSONL for a session.

    Checks both {encoded_path}/{session_id}.jsonl and the directory format.
    """
    encoded = encode_project_path(project_path)
    proj_dir = PROJECTS_DIR / encoded
    messages = []

    # Try flat file first
    jsonl = proj_dir / f"{session_id}.jsonl"
    if jsonl.exists():
        messages = _read_jsonl(jsonl)

    # Also check directory format (subagent sessions)
    session_dir = proj_dir / session_id
    if session_dir.is_dir():
        for sub in sorted(session_dir.glob("**/*.jsonl")):
            messages.extend(_read_jsonl(sub))

    return messages


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


def compute_costs_fallback(meta: dict) -> dict:
    """Fallback cost estimate from session-meta aggregates (no cache breakdown)."""
    inp = meta.get("input_tokens", 0)
    out = meta.get("output_tokens", 0)
    rates = PRICING["opus"]
    costs = {
        "input": cost_per_m(inp, rates["input"]),
        "cache_write_5m": 0.0,
        "cache_write_1h": 0.0,
        "cache_read": 0.0,
        "output": cost_per_m(out, rates["output"]),
        "model_family": "opus",
        "dominant_model": "unknown (estimated)",
    }
    costs["total"] = costs["input"] + costs["output"]
    return costs


def detect_issues(token_totals: dict, costs: dict, meta: dict, facet: dict | None) -> list[dict]:
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
    errors = meta.get("tool_errors", 0)
    if errors > 0:
        cats = meta.get("tool_error_categories", {})
        cat_str = ", ".join(f"{k}: {v}" for k, v in cats.items())
        issues.append({
            "type": "tool_errors",
            "detail": f"{errors} tool error(s) ({cat_str})",
            "fix": "Review error patterns, add permission rules or fix tool configuration.",
        })

    # Low satisfaction
    if facet:
        helpfulness = facet.get("claude_helpfulness", "")
        if helpfulness and helpfulness not in ("essential", "very_helpful"):
            issues.append({
                "type": "low_satisfaction",
                "detail": f"Session helpfulness rated '{helpfulness}'",
                "fix": "Session had low effectiveness — review for scope or communication issues.",
            })

        # Friction
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


def analyze_single_session(session_id: str, project_path: str) -> dict:
    """Full analysis of a single session."""
    meta = load_session_meta(session_id)
    if not meta:
        return {"error": f"Session meta not found for {session_id}"}

    facet = load_facet(session_id)
    transcript = load_transcript(session_id, project_path)

    has_transcript = bool(transcript)
    if has_transcript:
        token_totals = analyze_transcript_tokens(transcript)
        costs = compute_costs(token_totals)
    else:
        token_totals = {
            "input_tokens": meta.get("input_tokens", 0),
            "cache_write_5m_tokens": 0,
            "cache_write_1h_tokens": 0,
            "cache_read_tokens": 0,
            "output_tokens": meta.get("output_tokens", 0),
            "models": {},
            "high_output_turns": [],
            "assistant_message_count": meta.get("assistant_message_count", 0),
        }
        costs = compute_costs_fallback(meta)

    issues = detect_issues(token_totals, costs, meta, facet)

    return {
        "session_id": session_id,
        "project_path": meta.get("project_path", project_path),
        "meta": meta,
        "facet": facet,
        "token_totals": token_totals,
        "costs": costs,
        "issues": issues,
        "has_transcript": has_transcript,
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
    sessions = find_all_project_sessions(project_path)
    if not sessions:
        return {"error": f"No sessions found for project: {project_path}"}

    all_analyses = []
    total_cost = 0.0
    total_input = 0
    total_output = 0
    tool_usage = {}
    tool_errors_by_tool = {}
    outcomes = {}
    helpfulness_scores = []
    friction_types = {}
    session_types = {}
    durations = []

    for meta in sessions:
        sid = meta.get("session_id", "")
        analysis = analyze_single_session(sid, project_path)
        if "error" in analysis:
            continue
        all_analyses.append(analysis)

        cost = analysis["costs"]["total"]
        total_cost += cost
        total_input += analysis["token_totals"]["input_tokens"]
        total_output += analysis["token_totals"]["output_tokens"]

        dur = meta.get("duration_minutes", 0)
        if dur:
            durations.append(dur)

        # Aggregate tool usage
        for tool, count in meta.get("tool_counts", {}).items():
            tool_usage[tool] = tool_usage.get(tool, 0) + count

        errors = meta.get("tool_errors", 0)
        if errors > 0:
            for tool in meta.get("tool_error_categories", {}):
                tool_errors_by_tool[tool] = tool_errors_by_tool.get(tool, 0) + meta["tool_error_categories"][tool]

        # Facet aggregation
        facet = analysis.get("facet")
        if facet:
            outcome = facet.get("outcome", "unknown")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1

            h = facet.get("claude_helpfulness", "")
            if h in HELPFULNESS_SCORES:
                helpfulness_scores.append(HELPFULNESS_SCORES[h])

            for ftype, count in facet.get("friction_counts", {}).items():
                friction_types[ftype] = friction_types.get(ftype, 0) + count

            stype = facet.get("session_type", "unknown")
            if stype not in session_types:
                session_types[stype] = {"count": 0, "total_cost": 0.0}
            session_types[stype]["count"] += 1
            session_types[stype]["total_cost"] += cost

    n = len(all_analyses)
    costs_list = [a["costs"]["total"] for a in all_analyses]

    # Trend: split into halves
    half = n // 2
    first_half = all_analyses[:half] if half > 0 else []
    second_half = all_analyses[half:] if half > 0 else all_analyses

    def avg_cost(group):
        if not group:
            return 0.0
        return sum(a["costs"]["total"] for a in group) / len(group)

    sorted_costs = sorted(costs_list)
    median_cost = sorted_costs[len(sorted_costs) // 2] if sorted_costs else 0.0

    return {
        "project_path": project_path,
        "session_count": n,
        "time_span": {
            "first": sessions[0].get("start_time", "?"),
            "last": sessions[-1].get("start_time", "?"),
        },
        "total_cost": total_cost,
        "mean_cost": total_cost / n if n else 0,
        "median_cost": median_cost,
        "max_cost": max(costs_list) if costs_list else 0,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_duration_minutes": sum(durations),
        "tool_usage": dict(sorted(tool_usage.items(), key=lambda x: -x[1])),
        "tool_errors": tool_errors_by_tool,
        "outcomes": outcomes,
        "avg_helpfulness": sum(helpfulness_scores) / len(helpfulness_scores) if helpfulness_scores else None,
        "friction_types": dict(sorted(friction_types.items(), key=lambda x: -x[1])),
        "session_types": session_types,
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

    meta = analysis["meta"]
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
    lines.append(f"| Started | {meta.get('start_time', '?')} |")
    lines.append(f"| Duration | {meta.get('duration_minutes', '?')} min |")
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
    data_source = "Transcript" if analysis["has_transcript"] else "Estimated (session-meta only)"
    lines.append(f"## Token Breakdown ({data_source})\n")
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
    tool_counts = meta.get("tool_counts", {})
    if tool_counts:
        lines.append("## Tool Usage\n")
        lines.append("| Tool | Calls | Errors |")
        lines.append("|------|-------|--------|")
        error_cats = meta.get("tool_error_categories", {})
        sorted_tools = sorted(tool_counts.items(), key=lambda x: -x[1])
        for tool, count in sorted_tools:
            lines.append(f"| {tool} | {count} | — |")
        if meta.get("tool_errors", 0) > 0:
            lines.append(f"| **Total errors** | | **{meta['tool_errors']}** ({', '.join(f'{k}: {v}' for k, v in error_cats.items())}) |")
        lines.append("")

    # Timeline
    lines.append("## Timeline\n")
    dur = meta.get("duration_minutes", 0)
    user_msgs = meta.get("user_message_count", 0)
    asst_msgs = meta.get("assistant_message_count", 0)
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
    resp_times = meta.get("user_response_times", [])
    if resp_times:
        avg_resp = sum(resp_times) / len(resp_times)
        lines.append(f"| Avg user response time | {avg_resp:.0f}s |")
    lines.append("")

    # Efficiency
    la = meta.get("lines_added", 0)
    lr = meta.get("lines_removed", 0)
    fm = meta.get("files_modified", 0)
    if la + lr > 0 or fm > 0:
        lines.append("## Efficiency\n")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Lines added | {la} |")
        lines.append(f"| Lines removed | {lr} |")
        lines.append(f"| Files modified | {fm} |")
        out_k = tt["output_tokens"] / 1000 if tt["output_tokens"] > 0 else 1
        lines.append(f"| Lines changed per 1K output tokens | {(la + lr) / out_k:.1f} |")
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
    lines.append("## Overview\n")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Project | `{analysis['project_path']}` |")
    lines.append(f"| Total sessions | {analysis['session_count']} |")
    lines.append(f"| Time span | {analysis['time_span']['first'][:10]} to {analysis['time_span']['last'][:10]} |")
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
        diff = trend["second_half_avg_cost"] - trend["first_half_avg_cost"]
        if trend["first_half_avg_cost"] > 0:
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

    if analysis["tool_errors"]:
        lines.append("## Tool Errors\n")
        lines.append("| Category | Count |")
        lines.append("|----------|-------|")
        for cat, count in sorted(analysis["tool_errors"].items(), key=lambda x: -x[1]):
            lines.append(f"| {cat} | {count} |")
        lines.append("")

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
        lines.append(f"## Average Helpfulness\n")
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

    # Session type costs
    if analysis["session_types"]:
        lines.append("## Session Type Costs\n")
        lines.append("| Type | Sessions | Avg Cost |")
        lines.append("|------|----------|----------|")
        for stype, data in sorted(analysis["session_types"].items(), key=lambda x: -x[1]["total_cost"]):
            avg = data["total_cost"] / data["count"] if data["count"] > 0 else 0
            lines.append(f"| {stype} | {data['count']} | {fmt_cost(avg)} |")
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
    parser.add_argument("--output", default="./session-analysis.md", help="Output file path")
    args = parser.parse_args()

    project_path = os.path.normpath(args.project)

    if args.scope == "project":
        analysis = analyze_project(project_path)
        report = render_project_report(analysis)
    else:
        if args.session_id == "latest":
            latest = find_latest_session(project_path)
            if not latest:
                print(f"Error: No sessions found for project: {project_path}", file=sys.stderr)
                sys.exit(1)
            session_id = latest["session_id"]
        else:
            session_id = args.session_id

        analysis = analyze_single_session(session_id, project_path)
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
