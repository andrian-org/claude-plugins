---
name: dgf-security
description: Run the application's security scan — runtime and framework versions, NuGet and npm dependencies, secrets in the files and git history, Docker and web.config settings, the source code, container images, a running test site and the SBOM — and relay its step table, result and report. Needs Docker or the scanners installed; writes only its reports. Use for "security check", "security scan", "scan for vulnerabilities", "check for secrets", "is this secure", "SBOM", "dgf security".
argument-hint: "[--url <test url>] [--image <name>[,<name>…]] [--build [--dockerfile <file>]] [<folder>]"
allowed-tools: Read Glob Grep Bash(bash "{{dgf_runtime}}/scripts/security-scan.sh" *) AskUserQuestion
disable-model-invocation: false
version: 0.1.0
---

# DGF Security — The Application's Security Scan

One script, `security-scan.sh`, runs eight steps over the application and writes one readable report
per run:

| Step | What it checks |
|---|---|
| 1. Runtime and framework versions | every .NET, Node.js, Angular, React and Next.js version still receives security fixes, and each runtime is on a patch that has them |
| 2. Dependencies | the NuGet and npm packages that ship, against published advisories |
| 3. Secrets | passwords, keys and tokens in the files and in git history — redacted in the report |
| 4. Configuration | Dockerfiles, Kubernetes, Helm, Terraform and `web.config`, for unsafe settings |
| 5. Code (SAST) | the source code, with Semgrep's rules for the languages found |
| 6. Container image | the images you ship — only with `--image` or `--build` |
| 7. Running application (DAST) | an OWASP ZAP baseline of a running **test** site — only with `--url`; it does not attack the site |
| 8. SBOM | every component of this release, as CycloneDX files kept with the report |

**This is the application's security, not the DGF configuration's health.** The scan reads lock files,
Dockerfiles, source code, images and a running site — the host and the code around the workspaces. The
configuration's health — validators, references, the reference graph — is `/dgf-audit` (ADR 0034 §1).

**A skipped check is never a pass.** The scan uses each scanner when it is installed, otherwise its pinned
Docker image. With neither, a step cannot run: it is a `SKIP` row, and the run exits `2`, not `0`. The scan
needs the network for advisories, release data and images.

This skill writes nothing itself and emits no `dgf-gate-result` block: the scan's report is the result.

## Workflow

### Step 0: Context

1. **The project folder** — `<project>`. A folder the user named. Otherwise the current folder, when it holds
   `.dgf-factory/`. Otherwise ask with `AskUserQuestion` which folder to scan — the folder that holds the
   application's solution, Dockerfiles and `.dgf-factory/` — and **STOP** until it is answered.
2. **The report folder** — `<paths.security>`. Read `<project>/.dgf-factory/config.yaml` when it exists and take
   `paths.security`; when the file or the key is absent, `.dgf-factory/security/`. It is relative to
   `<project>`. Read `language.ui` from the same file for the summary, when present.

### Step 1: Options

The scan runs steps 1–5 and 8 with no option. Add an option only when the user's request names it:

| Option | When |
|---|---|
| `--url "<url>"` | Only for a URL the user names **and** says is a test environment. If they have not said so, ask with `AskUserQuestion` whether it is a test environment; on anything but a clear yes, run without `--url` and say step 7 was not run. **Never a production URL**: ZAP sends real requests to the site. |
| `--image "<name>[,<name>…]"` | The user names built container images to scan (step 6) and to add to the SBOM. |
| `--build` | The user asks to build the image from the project's `Dockerfile` and scan it; with `--dockerfile "<file>"` when they name another Dockerfile, relative to `<project>`. |
| `--severity "<list>"`, `--history <n>` | Only when the user asks for other blocking severities (default `HIGH,CRITICAL`) or a shorter history scan (default `0`, every commit). |

Never add `--skip` unless the user asks to skip a step by name.

### Step 2: Run the scan

```bash
bash "{{dgf_runtime}}/scripts/security-scan.sh" --path "<project>" --out "<project>/<paths.security>"
```

— with the options from Step 1 appended. The scan can run for many minutes (a dependency restore, an image
pull, a slow advisory feed): give the command a long timeout, and never cut it short to read partial output.
Capture the exit code before anything reads the output: a pipe would report the pipe's own. The last line is
the verdict, after the `RESULT:`, `INCOMPLETE:` and `Report:` lines.

| Exit | Action |
|---|---|
| `0` | `CLEAN`: every check that ran passed, and none was skipped. Relay (Step 3). |
| `1` | `BLOCKED`: at least one `FAIL` row. Relay (Step 3), leading with the `FAIL` rows: do not release until each is fixed or has an approved exception. |
| `2` | `WARNINGS`: a `WARN` row to check by hand, or a `SKIP` row — a check that did not run. Relay (Step 3); name each skipped check and what its row asks for (a scanner, Docker, the dotnet SDK), and say the result is incomplete. |
| `3` | **STOP** and relay its message verbatim: a usage error or a run that could not start (not a folder, no report folder). Correct the call, or ask for the folder. |
| any other | **STOP**: the scan did not run. `127` means `{{dgf_runtime}}/scripts/security-scan.sh` is missing — run `/dgf-doctor`, then `dgf-factory setup`. |

### Step 3: Relay

Relay, in this order, verbatim where the text is the script's:

1. **The step table** — each row the scan printed: the check, `PASS`, `WARN`, `FAIL` or `SKIP`, and its finding.
   Every `SKIP` row stays visible as a check that did not run; never call it passed.
2. **The `RESULT:` line**, and the `INCOMPLETE:` line when there is one.
3. **The report path** from the `Report:` line. Its raw scanner output is in the `<date>_<time>_raw/` folder
   beside it.
4. **What to fix first** — read the report and relay its `## What to do next` list verbatim, in its order:
   secrets first, then dependencies, images, runtimes, the running site, configuration and code.
5. **The verdict** — the last line, `CLEAN`, `WARNINGS` or `BLOCKED`.

Summarise in `language.ui` around those lines, never in place of them. Quote a finding by its file and line, as
the report does; never print a secret's value.

### Step 4: Next

- `FAIL` rows → fix each as the report's **How to fix** says, then run `/dgf-security` again. A real secret is
  rotated at its provider first: removing it from the code does not remove it from git history.
- `SKIP` rows → install what the row asks for (Docker, or the scanner it names), then run `/dgf-security` again,
  so the result is complete.
- `WARN` rows → a person checks each one; the report's section says what to look for.
- The DGF configuration's health → `/dgf-audit`. A change to the configuration → `/dgf-plan`.

## Execution Rules

### DO:

- ✅ Run the scan once per request, with `--out` under `<paths.security>`, and capture its exit code before any pipe
- ✅ Relay the step table, the `RESULT:` line, the report path and the report's `## What to do next` list verbatim
- ✅ Keep every `SKIP` row visible as a check that did not run
- ✅ Confirm a URL is a test environment before passing `--url`

### DON'T:

- ❌ Install, update or pull a scanner, Docker or an SDK — say what a `SKIP` row needs, and let the user install it
- ❌ Pass `--skip` unless the user asks to skip that step
- ❌ Scan a URL the user did not name as a test environment, or any production URL
- ❌ Print a secret's value — the report redacts them; do not open the files a secret finding names to show one
- ❌ Call a `SKIP`, a `WARN` or a not-run step a pass
- ❌ Write, edit or delete any file, or emit a `dgf-gate-result` block

## Artifact Ownership

- **Writes:** nothing itself. The scan writes only under `<project>/<paths.security>`: one
  `<date>_<time>_security-report.md` and one `<date>_<time>_raw/` folder per run, and a `.gitignore` of `*` in a
  report folder it creates, so no report reaches a commit by accident.
- **Reads:** `.dgf-factory/config.yaml`, the scan's output and its report.

## Critical Rules

1. **The scan decides.** Its exit code and its rows are the result; this skill relays them and adds no verdict.
2. **A skipped check is never a pass.** Exit `2` with `SKIP` rows means the result is incomplete.
3. **Test environments only.** `--url` is passed only for a URL the user named as a test environment.
4. **Nothing installed, nothing skipped unasked, no secret printed.**
5. **`{{dgf_runtime}}` always** for dgf-factory's own scripts.
