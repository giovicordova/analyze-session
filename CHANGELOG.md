# Changelog

## [3.0.0] - 2026-03-08

### Changed
- **Breaking:** Rewrote data layer to read JSONL transcripts from `~/.claude/projects/` instead of stale `usage-data/session-meta/` snapshot
- Renamed plugin from `analyze-session` to `sa`, skill from `analyze` to `run` — command is now `/sa:run`
- Added `marketplace.json` for global installation via `claude plugin marketplace add`
- Removed Stop hook from `hooks/hooks.json` — analysis only runs on command
- Session metadata (duration, tool counts, message counts) now extracted directly from transcripts
- Fallback to `cache_creation_input_tokens` when detailed cache breakdown is absent

### Fixed
- Plugin now finds sessions for all projects (was reading from a stale 200-file snapshot)
- Path encoding handles both `/` and `_` replacement patterns

## [2.0.1] - 2026-03-07

### Added
- `disable-model-invocation: true` to SKILL.md — skill only runs when explicitly invoked
- `hooks/hooks.json.example` — copy-paste-ready Stop hook config for auto-analysis
- `.claude/settings.json` — dev permissions for running python3 scripts/tests without prompts

### Changed
- CLAUDE.md: replaced file tree with one-liner referencing README.md
- README.md: hook documentation now references `hooks/hooks.json.example`

## [2.0.0] - 2026-03-07

### Changed
- Unified `analyze-session` and `fix-session` into a single `run` skill
- Skill invocation is now `/sa:run` (was `/analyze-session:analyze`)
- Fix mode is now `--fix` flag on the unified skill (was separate `/analyze-session:fix-session`)

### Added
- `--apply` flag for auto-applying low-risk fixes (CLAUDE.md size checks, categorized suggestions)
- Runner script `run-analysis.sh` for standalone/hook usage with `--commit` support
- Test suite: `tests/sample-report.md` + `tests/validate-report.py`
- Enhanced report parser: extracts all sections, model, outcome, duration
- CHANGELOG.md

### Fixed
- fix-report.py now parses all report sections (was limited to issues/fixes/actions)
- Cost extraction handles comma-separated and bold-wrapped values

## [1.0.0] - 2026-03-05

### Added
- Initial release with analyze-session and fix-session skills
- Single session and project-scope analysis
- Token/cost breakdown with full cache detail
- Tool usage ranking with error tracking
- Quality metrics from Claude's facets
- Issue detection with fix suggestions
