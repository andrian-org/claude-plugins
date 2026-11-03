---
id: 0034
title: "The security scan ships in the runtime behind /dgf-security, and migration and upgrade are guided routes, not skills"
status: accepted
date: 2026-11-03
deciders: [Andrian Mamei]
supersedes: []
tags: [security, guides, scope, migration, upgrade]
---

# 0034 — The security scan ships in the runtime behind /dgf-security, and migration and upgrade are guided routes, not skills

**Status: accepted** (2026-11-03, Andrian Mamei), under the delegation recorded in
[ADR 0032](0032-quality-and-authoring-skills.md).

Roadmap milestone **Usage Guides** asks for three decisions before its guides can be written: where
`scripts/security-scan.sh` lives and how a skill calls it, whether a migration skill is in scope, and what the
upgrade route is when no upgrade skill exists. This ADR makes the three.

## Context

Read on **2026-11-03** from this repository.

- **The scan is untracked inside the shipped `scripts/`.** `package.json` ships `scripts/` whole, so `npm pack`
  would ship it as it stands. It orchestrates Trivy, Gitleaks, Semgrep and OWASP ZAP over eight steps —
  runtime versions, dependencies, secrets, configuration, code, image, DAST, SBOM — falling back to pinned
  Docker images for any tool not installed, and writes a Markdown report and the raw output per run.
- **Its exits break the contract.** It exits `2` for a usage error, where `.ai-factory/rules/base.md` and
  `docs/skill-authoring.md` say `3`, and `2` means warnings; a run with skipped steps exits `0`, reading as a
  pass. Its header names a `security-scan.ps1` Windows twin that does not exist.
- **It reads the application, not the configuration.** Its inputs are lock files, Dockerfiles, source code,
  images and a running URL — the host and the code around the workspaces, which no dgf-factory validator
  reads. `/dgf-audit` is the configuration's health and writes nothing (ADR 0027 §5).
- **Migration has no deterministic source.** An "old project" is any system: its entities, processes and
  screens are in a schema this plugin has no reader for. `/dgf-scaffold` already creates an application from
  one design file (ADR 0026 §2, ADR 0027 §7), and every change after it is brownfield (ADR 0026 §1).
- **Upgrade has every part but a skill.** `/dgf` records the declared version (ADR 0019); the knowledge is
  stamped to one DGF version and re-vendored by a maintainer (ADR 0013); the dgf-mcp server serves
  `get_release_notes("since:X.Y.Z")`; `/dgf-explore` (ADR 0032) researches against it; the verify gate and
  `/dgf-audit` check the whole root.

## Decision

### 1. The scan ships in the runtime, behind its own skill

- `scripts/security-scan.sh` stays where it is, shipped, and is installed into `.dgf-factory/runtime/scripts/`
  like every script. It is the only shell script a skill runs.
- **Its exits join the contract:** `0` every step that ran passed and none was skipped; `1` a blocking finding;
  `2` warnings or a skipped step — a skipped step is a check that did not run, never a pass; `3` a usage error
  or a run that could not start. It prints the house verdict word last — `CLEAN`, `WARNINGS` or `BLOCKED` —
  after its `RESULT:` and `Report:` lines.
- **No Windows twin is claimed.** The header says macOS, Linux and WSL.
- **Its reports never reach a commit by accident:** an output folder the scan creates gets a `.gitignore` of `*`.
- **`/dgf-security`** runs it with `--out <paths.security>` (default `.dgf-factory/security/`), relays the step
  table, the result and the report path, and writes nothing else. It is read-only toward the estate and
  pre-approves only `Bash(bash "{{dgf_runtime}}/scripts/security-scan.sh" *)`. It needs Docker or the scanners
  installed; without either, every step is a skip, and the run is `2`, not a pass.

### 2. No migration skill

A migration from a non-DGF system is out of scope. The guide's route is an assessment: what of the estate is
already DGF (`/dgf-audit`), the target written as a `/dgf-scaffold` design for a new application or as
`/dgf-plan` plans in an existing one, and the old system read by a person. A migration skill is reconsidered
when a source system with a machine-readable model recurs across estates.

### 3. Upgrade is a guided route

No upgrade skill ships. The route: update dgf-factory (`npm update`, then `dgf-factory setup`) for knowledge
stamped nearer the target version; `/dgf-explore` over `get_release_notes("since:<declared>")` for the breaking
changes, cited; re-run `/dgf` to declare the new version; `/dgf-audit` and a plan per breaking change;
`/dgf-verify` over the whole root. Where the knowledge's stamp is older than the target, the guide says so, and
the facts are re-verified through the docs MCP.

## Alternatives considered

- **Move the scan to `tools/`.** Rejected: `tools/` is maintainer-only, and the scan is for the estate's own team.
- **Run the scan from `/dgf-audit`.** Rejected: the audit writes nothing and reads configuration; the scan writes
  reports and reads the application.
- **Write a `security-scan.ps1`.** Rejected for now: untested on Windows; WSL runs the shell script.
- **A migration skill that reads an old schema by prompt.** Rejected: determinism before prompting; no script can
  check what it produces against the source.

## Consequences

### Positive

- The security check the roadmap names has a skill, an exit the pipeline understands, and no false pass.
- The guides can name a skill for every step they describe, or say plainly that none exists.

### Negative

- The scan depends on Docker or seven installed tools, and on the network for advisories and images.
- Migration remains a manual assessment.
- An upgrade is only as current as the shipped knowledge stamp.

### Follow-ups

- A Windows-native scan, if an estate team needs one.
- An upgrade check that compares `dgf.version` with the knowledge stamp and lists the release notes between them.
