<!-- kano-agent-backlog-skill:start -->
## Backlog workflow (kano-agent-backlog-skill)
- Skill entrypoint: `{{SKILL_ROOT}}/SKILL.md`
- Backlog root: `{{BACKLOG_ROOT}}`
- Before coding, create/update backlog items and meet the Ready gate.
- Worklog is append-only; record decisions and state changes.
- Prefer running the skill scripts so actions are auditable (and dashboards stay current):
  - `python {{SKILL_ROOT}}/scripts/backlog/workitem_create.py --agent <agent-name> ...`
  - `python {{SKILL_ROOT}}/scripts/backlog/workitem_update_state.py --agent <agent-name> ...`
  - `python {{SKILL_ROOT}}/scripts/backlog/view_refresh_dashboards.py --agent <agent-name> --backlog-root {{BACKLOG_ROOT}}`
- Dashboards auto-refresh after item changes by default (`views.auto_refresh=true`); use `--no-refresh` or set it to `false` if needed.
<!-- kano-agent-backlog-skill:end -->
