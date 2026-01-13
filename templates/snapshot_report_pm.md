# Product Manager Snapshot Report: {{scope}}

**Generated:** {{meta.timestamp}}
**Version:** {{meta.git_sha}}

## Feature Delivery Status

Overview of feature implementation based on repository evidence.

### Done / In Review
{{#each capabilities}}
  {{#if (eq status "done")}}
- [x] **{{feature}}**
  - _Evidence:_ {{#each evidence_refs}}{{this}}; {{/each}}
  {{/if}}
{{/each}}


### In Progress / Partial
{{#each capabilities}}
  {{#if (eq status "partial")}}
- [/] **{{feature}}**
  - _Status:_ Partial / In Progress
  - _Evidence:_ {{#each evidence_refs}}{{this}}; {{/each}}
  {{/if}}
{{/each}}


### Not Started / Missing
{{#each capabilities}}
  {{#if (eq status "missing")}}
- [ ] **{{feature}}**
  {{/if}}
{{/each}}

## Known Risks (Stubs)
The following items have explicit code markers indicating incomplete work:

{{#each stub_inventory}}
- **{{type}}** in `{{file}}`: "{{message}}" {{#if ticket_ref}}(Ticket: {{ticket_ref}}){{/if}}
{{/each}}
