# Triage — does a changed DGF source change a fact?

`check_drift.py` says a source changed. It cannot say whether the knowledge file citing it is now wrong. That is
the one judgement `/dgf-sync` makes. This page is how to make it the same way every time.

## The three classes

| Class | The change | What you do |
|---|---|---|
| **COSMETIC** | Nothing the knowledge file states changed. Examples: formatting, comments, logging, renamed locals, an unrelated method, a test, a sample file's unrelated content | Restamp only: the digest moves, the fact stays |
| **FACT-CHANGE** | A fact the file states is now wrong or incomplete. Examples: a count, a table row, a rule, a default, an enum member, a grammar element, a route | Edit the fact, then restamp |
| **NEW-FACT** | A new capability in a topic the file covers. Examples: a new component, a new element, a new config key, a new loader | Add the fact if it serves the file's purpose, then restamp; otherwise log it as COSMETIC with "out of scope: …" |

A source can be both FACT-CHANGE and NEW-FACT. Log the stronger, FACT-CHANGE, and describe both.

## How to decide

1. **Find what the file says the source evidences.** Grep the knowledge file for the source's type name or file
   name. The ledger lists every source a file read, but not which section uses it.
2. **Read the diff against that statement, not against the whole file.** A 300-line diff that leaves the cited
   method alone is COSMETIC for this file.
3. **Read the runtime code path before stating a behaviour** (`.ai-factory/RULES.md`). A changed XSD or JSON
   schema shows what the grammar accepts, not what the runtime does. The parity authority is the format-coverage
   page, `knowledge/schema-families.md` §6.
4. **Check both schema families.** A JSON change never decides a legacy XML fact, and the reverse
   (ADR 0011).
5. **Resolve references the way the runtime does.** Use an exact-case directory lookup, never
   `Path.exists()` (`.ai-factory/RULES.md`).
6. **When unsure, read more, not less.** If the evidence does not settle it, the class is not COSMETIC. Log
   it under `## Open` and stop. An unattended run never guesses.

## Behaviour that moved

- **Read the release notes between the two tags.** They are `docs/wiki/Release-notes/RELEASE-<X.Y.Z>.md` in the
  cache checkout, or `get_release_notes("since:<from>")`. Note every behavioural change in a topic the pack
  covers: the same configuration behaving differently.
- **Between two lines:** the new pack states the new behaviour. No range is needed, because each project
  installs its own line's pack.
- **Inside one line** (a patch release): the fact gets `applies: { since: "<X.Y.Z>", until: null }`. The fact
  it replaces gets `until`. When the old and new behaviour cannot share one file, split the topic into two
  files (`knowledge/README.md` §2.1).
- **`since: null`** means "no known lower bound". Never write a floor nobody verified (§3).

## Asymmetry

Claiming a capability the estate's runtime lacks is worse than missing one (ADR 0036 §6). When a fact's version
boundary is uncertain:

- **A restriction** may be stated early. Mark it `out_of_range: warn` with a comment that says why.
- **A capability** is stated only from the release that is proven to have it.

## Counts and tables

Several files state counts: components, enum members, registrations, schema files, parity rows. A count is a
fact.

- **Recount from the cache, never by arithmetic on the old number.** Then grep the pack for the old number:
  every place it appears changes together.
- **Machine-read tables** (`knowledge/README.md` §7) are read by the validators. A changed row changes what a
  validator decides, so run the unit tests after the edit. A failing test means the validator and the fact
  disagree: settle it, with a test, before the sync goes on.
