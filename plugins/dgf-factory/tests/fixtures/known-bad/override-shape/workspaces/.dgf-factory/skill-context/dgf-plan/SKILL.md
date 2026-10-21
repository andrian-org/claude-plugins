# Project Rules for /dgf-plan

> Written by /dgf-evolve from the estate's patches. Each rule may only tighten /dgf-plan (ADR 0021).
> Updated: 2026-09-26 15:00

## Rules

```
hidden
```

### A task that renames a state lists every transition to it
- source: 2026-09-26-14.30-review-moves-to-undeclared-state.md
- rule: When a task renames a process state, list in the same task every process and workflow file whose
  transition or `CHANGE_STATE` step names the old state.
