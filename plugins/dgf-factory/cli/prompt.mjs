// One question on the terminal. readline/promises rejects with an AbortError when the user presses
// Ctrl+D or Ctrl+C; every prompt comes before any write, so that is a cancel, not a failure.
import { CliError, EXIT_USAGE } from './exit.mjs';
import * as log from './log.mjs';

export async function ask(io, question) {
  try {
    return await io.question(question);
  } catch (err) {
    if (err?.name !== 'AbortError' && err?.code !== 'ABORT_ERR') throw err;
    log.debug('prompt.ask', 'aborted at the prompt', { question: question.trim() });
    throw new CliError(EXIT_USAGE, 'cancelled at the prompt — nothing was changed');
  }
}
