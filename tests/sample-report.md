# Session Analysis Report

## Summary

| Field | Value |
|-------|-------|
| Session ID | `test-abc-123` |
| Project | `/Users/test/myproject` |
| Started | 2026-03-07T10:00:00Z |
| Duration | 25 min |
| Model | claude-opus-4-6 |
| Total Cost | **$4.14** |
| Outcome | mostly_achieved |

## What Happened

Built a REST API with authentication endpoints. Added JWT token support and user registration flow.

## Token Breakdown (Transcript)

| Category | Tokens | Cost |
|----------|--------|------|
| Base Input | 39 | $0.0006 |
| Cache Write (5m) | 0 | $0.0000 |
| Cache Write (1h) | 110.9K | $3.33 |
| Cache Read | 535.0K | $0.80 |
| Output | 137 | $0.01 |
| **Total** | | **$4.14** |

## Tool Usage

| Tool | Calls | Errors |
|------|-------|--------|
| Read | 15 | — |
| Edit | 8 | — |
| Bash | 6 | — |
| Write | 3 | — |
| Grep | 2 | — |
| **Total errors** | | **2** (permission: 1, timeout: 1) |

## Timeline

| Metric | Value |
|--------|-------|
| Duration | 25 min |
| User messages | 12 |
| Assistant messages | 18 |
| Total tool calls | 34 |
| Messages/min | 1.2 |
| Tools/min | 1.4 |

## Efficiency

| Metric | Value |
|--------|-------|
| Lines added | 245 |
| Lines removed | 32 |
| Files modified | 7 |
| Lines changed per 1K output tokens | 2024.8 |

## Quality

| Metric | Value |
|--------|-------|
| Outcome | mostly_achieved |
| Helpfulness | very_helpful |
| Session type | feature_development |
| Primary success | yes |

## Issues Found

1. **tool_errors** — 2 tool error(s) (permission: 1, timeout: 1)
2. **high_cache_cost** — Cache writes are 80% of total cost ($3.3300 of $4.1406)

## Recommended Fixes

### Tool Errors

**Problem:** 2 tool error(s) (permission: 1, timeout: 1)

**Fix:** Review error patterns, add permission rules or fix tool configuration.

### High Cache Cost

**Problem:** Cache writes are 80% of total cost ($3.3300 of $4.1406)

**Fix:** Use /compact, shorten system instructions, or reduce CLAUDE.md size.

## Next Actions

- [ ] Review error patterns, add permission rules or fix tool configuration.
- [ ] Use /compact, shorten system instructions, or reduce CLAUDE.md size.
