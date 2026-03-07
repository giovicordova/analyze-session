# Changelog

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
- Unified `analyze-session` and `fix-session` into a single `analyze` skill
- Skill invocation is now `/analyze-session:analyze` (was `/analyze-session:analyze-session`)
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
