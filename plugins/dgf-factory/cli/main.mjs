// dgf-factory — install the dgf-factory pipeline into a project, for each AI harness you use (ADR 0029).
import { parseArgs } from 'node:util';

import { CliError, EXIT_CLEAN, EXIT_USAGE, usageError } from './exit.mjs';
import * as log from './log.mjs';
import { packageVersion } from './paths.mjs';

// command → [loader, one-line summary]. Each module exports run(args) → exit code.
export const COMMANDS = {
  setup: [() => import('./commands/setup.mjs'), 'install or update dgf-factory in this project, for the harnesses you choose'],
  status: [() => import('./commands/status.mjs'), 'show what dgf-factory installed here, and what changed since'],
  uninstall: [() => import('./commands/uninstall.mjs'), 'remove what setup installed — only files you have not edited'],
};

export function usage() {
  const width = Math.max(0, ...Object.keys(COMMANDS).map((name) => name.length));
  const lines = Object.entries(COMMANDS).map(([name, [, summary]]) => `  ${name.padEnd(width)}  ${summary}`);
  return [
    'Usage: dgf-factory <command> [options]',
    '',
    'Commands:',
    ...lines,
    '',
    'Options:',
    '  --version  print the version and exit',
    '  --help     print this help and exit',
    '',
    'Exit codes: 0 clean, 1 blocked, 2 warnings, 3 usage error.',
    'Tracing: DEBUG=1 or LOG_LEVEL=debug|info prints to stderr.',
  ].join('\n');
}

export async function main(argv) {
  log.debug('main.main', 'argv', { argv });
  const [command, ...rest] = argv;
  if (command === undefined || command === '--help' || command === '-h') {
    process.stdout.write(`${usage()}\n`);
    return command === undefined ? EXIT_USAGE : EXIT_CLEAN;
  }
  if (command === '--version' || command === '-v') {
    process.stdout.write(`${packageVersion()}\n`);
    return EXIT_CLEAN;
  }
  if (!Object.hasOwn(COMMANDS, command)) {
    throw usageError(`unknown command \`${command}\`\n\n${usage()}`);
  }
  const [load] = COMMANDS[command];
  const module = await load();
  return module.run(rest, { parseArgs });
}

/** The bin's entry: run main(), print a failure, and set the exit code. Never called on import. */
export async function entry() {
  try {
    process.exitCode = await main(process.argv.slice(2));
  } catch (err) {
    if (err instanceof CliError) {
      log.debug('main.entry', 'failed', { code: err.code });
      process.stderr.write(`${err.message}\n`);
      process.exitCode = err.code;
      return;
    }
    if (err && err.code === 'ERR_PARSE_ARGS_UNKNOWN_OPTION') {
      process.stderr.write(`${err.message}\n\n${usage()}\n`);
      process.exitCode = EXIT_USAGE;
      return;
    }
    log.error('main.entry', 'unexpected failure', { error: String(err) });
    process.stderr.write(`${err && err.stack ? err.stack : err}\n`);
    process.exitCode = EXIT_USAGE;
  }
}
