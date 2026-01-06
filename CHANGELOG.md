# Changelog

All notable changes to `kano-agent-backlog-skill` will be documented in this file.

This project uses Git tags as releases: `vX.Y.Z`.

## [Unreleased]

### Added
- Optional SQLite index layer (rebuildable) to accelerate reads and view generation.
- DBIndex vs NoDBIndex demo dashboards under `_kano/backlog/views/_demo/`.
- Demo tool for recent/iteration focus views (`_kano/backlog/tools/generate_focus_view.py`).

### Changed
- Unified generated dashboards to prefer SQLite when enabled/available and fall back to file scan.
- Kept `scripts/backlog/generate_demo_views.py` self-contained; demo repo tool is a thin wrapper.

### Fixed
- `query_sqlite_index.py --sql` validation (SELECT/WITH detection).

## [0.0.1] - 2026-01-06

### Added
- Local-first backlog structure under `_kano/backlog/` (items, decisions/ADRs, views).
- Work item scripts: create items, validate Ready gate, update state with append-only Worklog.
- Audit logging for tool invocations with redaction and rotation.
- Plain Markdown dashboards + Obsidian Dataview/Bases demo views.
- Config system under `_kano/backlog/_config/config.json`.

### Changed
- Enforced explicit `--agent` for Worklog-writing scripts and auditability.

### Security
- Secret redaction and log rotation defaults for audit logs.
