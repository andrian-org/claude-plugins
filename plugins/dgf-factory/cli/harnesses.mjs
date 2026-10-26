// The AI harnesses dgf-factory installs into (ADR 0029 §3).
//
// The folders are AI Factory 2.19.0's registry, entry for entry: `dist/core/agents.js:7-174`
// (id, displayName, configDir, skillsDir, agentsDir, settingsFile). Keep them in step by hand;
// tests/cli/harnesses.test.mjs compares them with an installed ai-factory when one is found.
//
// Two fields are this tool's own:
//   transform  how a SKILL.md body's `/dgf-x` invocations are rewritten — AI Factory's
//              transformer per id (`dist/core/transformer.js:47-68`), reduced to what applies to
//              dgf-* skills: kilocode and antigravity flatten only AI Factory's own workflow
//              skills, so every dgf-* skill takes their default form.
//   mcp        where and in which shape setup writes the HTTP `dgf-mcp` entry (cli/mcp.mjs), or
//              null when the harness has no project-level MCP file setup can safely write: setup
//              prints a manual step instead. AI Factory's own MCP writer is stdio-only, so each was
//              read from the harness's own documentation on 2026-10-26 (ADR 0029, Errata):
//              - Kilo Code now keeps MCP in `kilo.jsonc`, JSON with comments, which cannot be merged
//                without losing them — manual. Windsurf (now Devin Desktop) has user-level config
//                only, and Zencoder's could not be read — manual.
//              - Codex CLI reads a project `.codex/config.toml` only once the user trusts the project.
import { usageError } from './exit.mjs';

export const HARNESSES = [
  { id: 'claude', displayName: 'Claude Code', configDir: '.claude', skillsDir: '.claude/skills', agentsDir: '.claude/agents', settingsFile: '.mcp.json', transform: 'default', mcp: { file: '.mcp.json', format: 'mcpServers-http' } },
  { id: 'cursor', displayName: 'Cursor', configDir: '.cursor', skillsDir: '.cursor/skills', settingsFile: '.cursor/mcp.json', transform: 'default', mcp: { file: '.cursor/mcp.json', format: 'mcpServers-url' } },
  { id: 'codex', displayName: 'Codex CLI', configDir: '.codex', skillsDir: '.codex/skills', agentsDir: '.codex/agents', settingsFile: null, transform: 'codex', mcp: { file: '.codex/config.toml', format: 'codex-toml' } },
  { id: 'codex-app', displayName: 'Codex app', configDir: '.agents', skillsDir: '.agents/skills', settingsFile: '.codex/config.toml', transform: 'codex', mcp: { file: '.codex/config.toml', format: 'codex-toml' } },
  { id: 'copilot', displayName: 'GitHub Copilot', configDir: '.github', skillsDir: '.github/skills', settingsFile: '.vscode/mcp.json', transform: 'default', mcp: { file: '.vscode/mcp.json', format: 'servers-http' } },
  { id: 'gemini', displayName: 'Gemini CLI', configDir: '.gemini', skillsDir: '.gemini/skills', settingsFile: null, transform: 'default', mcp: { file: '.gemini/settings.json', format: 'mcpServers-httpUrl' } },
  { id: 'junie', displayName: 'Junie', configDir: '.junie', skillsDir: '.junie/skills', settingsFile: null, transform: 'default', mcp: { file: '.junie/mcp/mcp.json', format: 'mcpServers-url' } },
  { id: 'qwen', displayName: 'Qwen Code', configDir: '.qwen', skillsDir: '.qwen/skills', settingsFile: '.qwen/settings.json', transform: 'qwen', mcp: { file: '.qwen/settings.json', format: 'mcpServers-httpUrl' } },
  { id: 'windsurf', displayName: 'Windsurf', configDir: '.windsurf', skillsDir: '.windsurf/skills', settingsFile: null, transform: 'default', mcp: null },
  { id: 'warp', displayName: 'Warp', configDir: '.warp', skillsDir: '.warp/skills', settingsFile: null, transform: 'default', mcp: { file: '.warp/.mcp.json', format: 'mcpServers-url' } },
  { id: 'zencoder', displayName: 'Zencoder', configDir: '.zencoder', skillsDir: '.zencoder/skills', settingsFile: null, transform: 'default', mcp: null },
  { id: 'roocode', displayName: 'Roo Code', configDir: '.roo', skillsDir: '.roo/skills', settingsFile: '.roo/mcp.json', transform: 'default', mcp: { file: '.roo/mcp.json', format: 'mcpServers-streamable' } },
  { id: 'kilocode', displayName: 'Kilo Code', configDir: '.kilocode', skillsDir: '.kilocode/skills', settingsFile: '.kilocode/mcp.json', transform: 'default', mcp: null },
  { id: 'antigravity', displayName: 'Antigravity', configDir: '.agent', skillsDir: '.agent/skills', settingsFile: null, transform: 'default', mcp: { file: '.agents/mcp_config.json', format: 'mcpServers-serverUrl' } },
  { id: 'opencode', displayName: 'OpenCode', configDir: '.opencode', skillsDir: '.opencode/skills', settingsFile: 'opencode.json', transform: 'default', mcp: { file: 'opencode.json', format: 'opencode-remote' } },
  { id: 'universal', displayName: 'Universal / Other', configDir: '.agents', skillsDir: '.agents/skills', settingsFile: '.mcp.json', transform: 'default', mcp: { file: '.mcp.json', format: 'mcpServers-http' } },
];

const BY_ID = new Map(HARNESSES.map((harness) => [harness.id, harness]));

export function harnessIds() {
  return HARNESSES.map((harness) => harness.id);
}

export function getHarness(id) {
  const harness = BY_ID.get(id);
  if (!harness) throw usageError(`unknown harness \`${id}\` — available: ${harnessIds().join(', ')}`);
  return harness;
}

/**
 * The harnesses for a list of ids, refusing two that would write one skills folder differently.
 * AI Factory refuses the same pair (`dist/core/transformer.js:79-102`): codex-app and universal
 * share `.agents/skills`, with different transforms.
 */
export function selectHarnesses(ids) {
  const unique = [...new Set(ids)];
  const chosen = unique.map(getHarness);
  const owner = new Map();
  for (const harness of chosen) {
    const first = owner.get(harness.skillsDir);
    if (first && first.transform !== harness.transform) {
      throw usageError(`\`${first.id}\` and \`${harness.id}\` both install into ${harness.skillsDir} but render skills differently — choose one`);
    }
    if (!first) owner.set(harness.skillsDir, harness);
  }
  return chosen;
}
