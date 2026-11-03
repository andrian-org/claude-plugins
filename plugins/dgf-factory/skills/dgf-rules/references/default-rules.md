# Rules

> Written by /dgf-rules. Each rule names how it is enforced; check_rules.py checks this file before any skill reads it.

## R1 — XML-always for the five legacy artifact types
- enforcement: script
- check: means-route
- source: default (ADR 0028 rule 1)

Generate XML for form, workflow, process, settings and view regardless of partial JSON schema parity.

This is the current generation policy of the shipped knowledge base (composition-specs §4). route_means.py names the family of every new file, and the verify gate holds a plan's new configuration files to their route.

## R2 — Declarative behaviour only
- enforcement: gate
- check: code-planned
- source: default (ADR 0028 rule 2)

Behaviour in FM/ artifacts is composed through DataFetcher and EventBase verbs, not hand-written JavaScript.

Workspaces legitimately hold JavaScript in their js/ folders, so the rule scopes to FM/ artifacts: behaviour that belongs in a declarative spec is not smuggled into one as script. A task that writes script or style is a kind: code task, with a reason that names the configuration route tried.

## R3 — Base-workspace edits need explicit justification
- enforcement: gate
- check: base-reason
- source: default (ADR 0028 rule 3)

A change under the base workspace (webasm/) is live in every application and must be named in the plan and verified against all consumers.

## R4 — DGF-seam scope discipline
- enforcement: prompt-only
- source: default (ADR 0028 rule 4)

Rules and review findings address DGF seams — components, specs, bindings, processes — not general C#, SQL or Angular style.

## R6 — Test stack
- enforcement: prompt-only
- source: default (ADR 0028 rule 6)

xUnit + FluentAssertions + Moq/NSubstitute (backend); Jest and Playwright (frontend).

This is a default, not an invariant: where DESCRIPTION.md records the estate's own test stack, the estate's stack is the one to name.

## R7 — Workspace layout
- enforcement: script
- check: layout-case
- source: default (ADR 0028 rule 7)

FM/_PROCESS, _WORKFLOW, _COMPONENTS, _DATA, _LOOKUP, _PROFILE and Services, plus _STORAGE at the workspace root — naming and casing.

These names are framework constants (composition-specs §1), and the runtime resolves them case-sensitively on Linux, so a folder whose name matches one only when case is ignored is never read there.
