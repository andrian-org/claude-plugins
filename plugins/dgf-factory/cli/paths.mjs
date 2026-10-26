import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import * as log from './log.mjs';

/** The installed package's root: the folder holding package.json, bin/, cli/ and the payload. */
export function packageRoot() {
  const root = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
  log.debug('paths.packageRoot', 'resolved', { root });
  return root;
}

export function packageJson(root = packageRoot()) {
  return JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
}

export function packageVersion(root = packageRoot()) {
  return packageJson(root).version;
}

/** A project-relative POSIX path, the form every receipt key and preview line uses. */
export function toPosix(rel) {
  return rel.split(path.sep).join('/');
}
