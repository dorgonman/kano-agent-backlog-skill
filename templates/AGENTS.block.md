<!-- kano-agent-backlog-skill:start -->
## Project backlog discipline (kano-agent-backlog-skill)
- Use `{{SKILL_ROOT}}/SKILL.md` for any planning/backlog work.
- Backlog root is `{{BACKLOG_ROOT}}` (items are file-first; index/logs are derived).
- Before any code change, create/update items in `{{BACKLOG_ROOT}}/items/` (Epic -> Feature -> UserStory -> Task/Bug).
- Enforce the Ready gate on Task/Bug before starting; Worklog is append-only.
- Use skill scripts (not ad-hoc edits) so audit logs capture actions:
  - Create: `python {{SKILL_ROOT}}/scripts/backlog/workitem_create.py --agent <agent-name> ...`
  - State: `python {{SKILL_ROOT}}/scripts/backlog/workitem_update_state.py --agent <agent-name> ...`
  - Views: `python {{SKILL_ROOT}}/scripts/backlog/view_refresh_dashboards.py --agent <agent-name> ...`
- Dashboards auto-refresh after item changes by default (`views.auto_refresh=true`); use `--no-refresh` or set it to `false` if needed.
<!-- kano-agent-backlog-skill:end -->
