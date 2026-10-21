---
plan_format: 1
mode: full                          # fast | full | ultra
branch: feature/zims-inspection-fee
created: 2026-09-25
affects_workspaces: [zims, webasm]  # never empty
base_workspace_reason: "The fee DataSource is shared by every application's payment page"
---

# Implementation Plan: Inspection fee

## Original Request

Show the inspection fee on the application form.

## Scope

- `zims`: the application form. `webasm`: the shared fee DataSource.

## Tasks

### Phase 1: Fee data
- [x] Task 1: Add the inspection-fee DataSource
  - kind: config
  - files: webasm/FM/_COMPONENTS/DataSource/InspectionFee.json
- [ ] **Task 2: Show the fee on the application form** (depends on 1)
  - kind: config
  - reason: the form already binds DataSources by name
  - files: `zims/FM/_DATA/Inspection/_forms/Apply/_form.xml`

### Phase 2: Behaviour
- [ ] Task 3: Hide the fee panel until the gateway confirms payment (depends on 1, 2)
  - kind: code
  - reason: No EventBase verb reads the gateway callback (knowledge/composition-specs.md §3.1)
  - files: zims/FM/_DATA/Inspection/_forms/Apply/_form.js
  - deletes: zims/js/legacy-fee.js

## Risks

- None known.

```markdown
## Tasks
- [ ] Task 99: inside a code fence, never a task
```
