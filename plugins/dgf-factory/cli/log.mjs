// Tracing to stderr, as the Python scripts trace: `DEBUG [<module>.<function>] <message> k=v …`.
// Off unless DEBUG=1 or LOG_LEVEL=debug|info|warn|error asks for it; WARN and ERROR always print.
// What the user reads — previews, reports — goes to stdout and never through here.

const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 };

function threshold() {
  if (process.env.DEBUG && process.env.DEBUG !== '0') return LEVELS.debug;
  return LEVELS[(process.env.LOG_LEVEL || '').toLowerCase()] ?? LEVELS.warn;
}

function pairs(data) {
  return Object.entries(data || {})
    .map(([key, value]) => `${key}=${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join(' ');
}

function write(level, where, message, data) {
  if (LEVELS[level] < threshold()) return;
  const tail = pairs(data);
  process.stderr.write(`${level.toUpperCase()} [${where}] ${message}${tail ? ` ${tail}` : ''}\n`);
}

export const debug = (where, message, data) => write('debug', where, message, data);
export const info = (where, message, data) => write('info', where, message, data);
export const warn = (where, message, data) => write('warn', where, message, data);
export const error = (where, message, data) => write('error', where, message, data);
