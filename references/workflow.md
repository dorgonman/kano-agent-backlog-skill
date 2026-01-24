# Workflow SOP

## A) Planning (discussion -> tickets)

1. Create or update Epic for the milestone.
2. Split into Features (capabilities).
3. Split into UserStories (user perspective).
4. Split into Tasks/Bugs (single focused coding sessions).
5. Fill Ready gate sections for each Task/Bug.
6. Append Worklog entry: "Created from discussion: ..." (scripts require `--agent`).

## B) Ready gate

- Move to Ready only after required sections are complete.
- No code changes until the item is Ready.

## C) Execution

1. Set state to InProgress.
2. Append Worklog for important decisions or changes.
3. If a decision is architectural, create ADR and link it:
   - Add ADR id to item `decisions: []`
   - Append Worklog entry referencing the ADR

### Conflict Guard

- **Owner Locking**: Items in `InProgress` are locked to their owner.
- **Auto-Assignment**: When moving to `InProgress`, if no owner is set, you become the owner.
- **Collaboration**: To hand off work, the current owner must change the owner field or move the item out of `InProgress` (e.g. to `Review` or `Planned`).

## D) Completion

1. Move state to Review -> Done.
2. Append a Worklog summary with:
   - What changed
   - Related items and ADRs

## D.1) Parent sync (forward-only)

- When a child state changes, parents can be auto-advanced forward-only.
- Parent edits never force child states.
- Use `--no-sync-parent` if you need to keep parent state unchanged for a manual re-plan.

## E) Scope change

- Do not rewrite a ticket into a different task.
- Split into a new ticket and link via `links.relates`.
- Append a Worklog entry explaining the split.

## F) File operations

- Use `scripts/backlog/*` or `scripts/fs/*` for backlog/skill artifacts.
- Scripts only operate under `_kano/backlog/` or `_kano/backlog_sandbox/` to keep audit logs clean.

## G) Artifacts directory

Store work outputs in `_kano/backlog/products/<product>/artifacts/<item-id>/`:

**What to store**:
- Demo reports (e.g., `DEMO_REPORT_*.md`)
- Implementation summaries (e.g., `*_IMPLEMENTATION.md`)
- Analysis documents and investigation results
- Test results and benchmark data
- Generated diagrams and visualizations
- Exported data or intermediate build artifacts

**Why**:
- **Traceability**: Artifacts are directly linked to the work item that produced them
- **Context**: All outputs related to a specific Epic/Feature/Task are co-located
- **Archival**: When an item is completed, all related artifacts are preserved together
- **Discovery**: Easy to find outputs by navigating to the item's artifacts directory

**Example**:
```
artifacts/
├── KABSD-EPIC-0003/
│   ├── DEMO_REPORT_0.0.2_FINAL_SUCCESS.md
│   ├── UID_VALIDATION_IMPLEMENTATION.md
│   └── benchmark_results.json
└── KABSD-TSK-0123/
    ├── analysis.md
    └── diagram.png
```

**Note**: Do not store artifacts in repo root or scattered locations; always use the structured artifacts directory.
