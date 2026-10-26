// Exit codes are a contract (.ai-factory/rules/base.md): every command returns one of these.
export const EXIT_CLEAN = 0;
export const EXIT_BLOCKED = 1;
export const EXIT_WARNINGS = 2;
export const EXIT_USAGE = 3;

/** A failure with the exit code it forces. Thrown anywhere; main() prints it and exits. */
export class CliError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

export function usageError(message) {
  return new CliError(EXIT_USAGE, message);
}
