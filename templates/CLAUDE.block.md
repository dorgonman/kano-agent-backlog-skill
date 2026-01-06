<!-- kano-agent-backlog-skill:start -->
## Backlog workflow (kano-agent-backlog-skill)
- Skill entrypoint: `{{SKILL_ROOT}}/SKILL.md`
- Backlog root: `{{BACKLOG_ROOT}}`
- Before coding, create/update backlog items and meet the Ready gate.
- Worklog is append-only; record decisions and state changes.
- Prefer running the skill scripts so actions are auditable (and dashboards stay current):
  - `python {{SKILL_ROOT}}/scripts/backlog/create_item.py --agent <agent-name> ...`
  - `python {{SKILL_ROOT}}/scripts/backlog/update_state.py --agent <agent-name> ...`
  - `python {{SKILL_ROOT}}/scripts/backlog/refresh_dashboards.py --agent <agent-name> --backlog-root {{BACKLOG_ROOT}}`
<!-- kano-agent-backlog-skill:end -->
