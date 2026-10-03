# dotGov Claude Code Plugins

Internal plugin marketplace for dotGov Solutions, named `andrian-org`. Hosted on GitHub — access
is controlled by the repo's permissions, so only teammates who can clone this repo can install
from it.

Repo: [`andrian-org/claude-plugins`](https://github.com/andrian-org/claude-plugins)

## For teammates: one-time setup

Run the first command in a **normal interactive terminal**, not inside a Claude Code session —
git may need to prompt for GitHub sign-in:

```bash
claude plugin marketplace add andrian-org/claude-plugins
claude plugin install doc-coverage-audit@andrian-org
claude plugin install dgf-factory@andrian-org
```

Restart Claude Code, then confirm:

```bash
claude plugin list
```

If the `add` fails with an authentication error, you are running non-interactively or have no
GitHub credential cached. Run `gh auth login` (or `git clone` the repo once by hand), then retry.

## Automatic provisioning (recommended)

Any project repo can declare this marketplace so teammates get the plugins with no setup at all.
Let the CLI write the entry rather than hand-authoring it:

```bash
cd /path/to/your/project
claude plugin marketplace add andrian-org/claude-plugins --scope project
```

That produces `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "andrian-org": {
      "source": {
        "source": "github",
        "repo": "andrian-org/claude-plugins"
      }
    }
  },
  "enabledPlugins": {
    "doc-coverage-audit@andrian-org": true,
    "dgf-factory@andrian-org": true
  }
}
```

Add `enabledPlugins` yourself. Commit the file — a fresh clone is then ready to go.

## Plugins

| Plugin | What it does |
|---|---|
| `doc-coverage-audit` | Maps a deliverables checklist to the documents that actually exist, with verified links and gap analysis. Built for close-out, hand-over, due diligence and audit evidence. |
| `dgf-factory` | A DotGov Framework-aware plan → implement → verify → commit pipeline, backed by deterministic validators that check both component config families — modern JSON and legacy XSD. |

## Contributing a plugin

```
plugins/<your-plugin>/
  .claude-plugin/plugin.json      # name, description, version, author
  skills/<skill-name>/SKILL.md    # frontmatter: name + description
  commands/  agents/  hooks/      # optional
```

The nesting matters: `skills/<skill-name>/SKILL.md`, not `skills/SKILL.md`. A flattened copy
(easy to cause with `cp -R`) will not load.

1. Scaffold with `claude plugin init <name>` for a starting point.
2. Add an entry to `.claude-plugin/marketplace.json` (`source: "./plugins/<your-plugin>"`).
3. Validate **both** manifests before opening a PR:

   ```bash
   claude plugin validate .
   claude plugin validate plugins/<your-plugin>
   ```

4. Test locally as a directory marketplace before pushing:

   ```bash
   claude plugin marketplace add /path/to/this/repo
   claude plugin install <your-plugin>@andrian-org
   claude plugin details <your-plugin>@andrian-org      # check token cost
   ```

5. If you also keep a copy in `~/.claude/skills/`, delete it — two registrations of the same
   skill name collide.

### Writing the `description`

The `description` in `SKILL.md` frontmatter is the **only** thing Claude sees when deciding
whether to load your skill. Write it as trigger phrases people actually type, not as a summary of
the implementation. Review descriptions in PRs more carefully than implementations — a good skill
with a vague description never fires.

### Keep an eye on token cost

`claude plugin details <name>@andrian-org` reports always-on cost, which every session pays. Keep
`SKILL.md` lean and push detail into `references/` files that load only when needed.

### Versioning and releases

Bump `version` in `plugin.json`, then:

```bash
claude plugin tag plugins/<your-plugin>
```

This creates `<name>--v<version>` and validates that `plugin.json` agrees with the marketplace
entry. Teammates update with `claude plugin update <name>` (restart required).

## Secrets

Never commit tokens, `.pfx`/`.jks`/`.pem` files, tenant credentials or client document content.
Skills must acquire credentials at runtime and cache them outside the repo — see `.gitignore`.
