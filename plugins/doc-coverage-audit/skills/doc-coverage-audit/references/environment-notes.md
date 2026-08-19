# Environment gotchas

Small things that break naive commands and cost real time. All observed on macOS + zsh inside a
sandboxed agent harness.

## Shell

| Trap | Fix |
|---|---|
| `timeout` does not exist on macOS | `gtimeout` (coreutils), or enforce the limit inside the script |
| Foreground `sleep` may be blocked by the harness | `perl -e 'select(undef,undef,undef,5)'` for 5 s |
| `cd` inside a compound command can trigger a permission prompt and reset the cwd | Use absolute paths everywhere |
| Paths with spaces, `&`, `(`, `)` — normal in SharePoint | Quote every expansion; `urllib.parse.quote` for URLs |
| Long recursive walks blow the 2-minute tool timeout | `nohup … > log 2>&1 &`, then poll for the output file |
| A heredoc-written helper is not executable | `chmod +x` after writing |

## Working in the background

Recursive enumeration is the slow part. Launch it and keep working:

```bash
nohup python3 walk_tree.py "$DRIVE" "$PATH" out.json > walk.log 2>&1 &
```

Poll for completion by testing for the output file rather than by trusting a PID — a finished
process and a crashed one both stop appearing in `ps`:

```bash
for i in $(seq 1 12); do
  [ -f out.json ] && break
  perl -e 'select(undef,undef,undef,20)'
done
cat walk.log
```

Write each walk to its own JSON file, then merge into one index. Chunked walks also survive
token expiry far better than one giant traversal.

## Blocked actions

A permission classifier or hook may block a command — commonly anything that reads credential
stores or posts to an auth endpoint. **This is the system working as intended.**

- Do not re-run the same call hoping for a different result.
- Do not seek the same secret by another route (keychain, token caches, config files). Searching
  the filesystem for cached credentials is exactly the behaviour the block exists to prevent.
- Do state plainly what you were trying to do, why it is needed, and what the alternatives are —
  then let the user choose. In the source session this turned a hard block into a one-question
  decision and the audit continued normally.

## Scratch files

Keep tokens, indexes and intermediate JSON in the session scratchpad directory, never in the
user's project tree. Only the final report belongs in their workspace.

## Handling secrets you stumble across

Enumeration surfaces things you were not looking for: `.pfx`, `.jks`, `.pem`, `.env`, keystores,
credential spreadsheets, VPN forms.

- Never open them, download them, or paste their contents.
- Never list them as a deliverable.
- Do record their existence and location in an **Exclusions** section as a hand-over warning.

Noting "these certificate files exist and must not ship to the client" is genuinely useful.
Reading them is not.
