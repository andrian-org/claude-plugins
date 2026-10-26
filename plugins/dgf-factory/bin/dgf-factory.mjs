#!/usr/bin/env node
const { entry } = await import('../cli/main.mjs');
await entry();
