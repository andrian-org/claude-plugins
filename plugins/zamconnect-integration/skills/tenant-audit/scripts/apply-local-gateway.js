// Applies a tenant's GATEWAY-CONFIG.md package to the LOCAL compose mongo only, in the order
// scope -> cluster -> route -> test user, then bumps the tokens YarpStatusWorker polls.
// Mirrors the AdminAPI entity shapes (Core/Database/Entities) and HashHelper's PBKDF2 settings.
const crypto = require('crypto');
const fs = require('fs');

const pkg = JSON.parse(fs.readFileSync(process.env.ZC_PACKAGE, 'utf8'));
const username = process.env.ZC_TEST_USER;
const password = process.env.ZC_TEST_PASSWORD;

const pascal = v => Array.isArray(v) ? v.map(pascal)
  : v && typeof v === 'object'
    ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k[0].toUpperCase() + k.slice(1), pascal(x)]))
    : v;
const bin = b => BinData(0, b.toString('base64'));
const now = new Date();
const out = { scopes: [], clusters: [], routes: [], user: null };

const routes = pkg.routes.map(r => ({ name: r.name, cfg: pascal(r.configJson) }));
const scopes = [...new Set(routes.map(r => r.cfg.Metadata && r.cfg.Metadata.Scope).filter(Boolean))];

for (const name of scopes) {
  const r = db.scopes.updateOne({ Name: name }, { $setOnInsert: { Name: name } }, { upsert: true });
  out.scopes.push(`${name}: ${r.upsertedCount ? 'created' : 'exists'}`);
}

for (const c of pkg.clusters) {
  const cfg = pascal(c.configJson);
  const r = db.clusters.updateOne({ 'ConfigJson.ClusterId': cfg.ClusterId },
    { $set: { Name: c.name, ConfigJson: cfg, Updated: now }, $setOnInsert: { Created: now } }, { upsert: true });
  out.clusters.push(`${cfg.ClusterId}: ${r.upsertedCount ? 'created' : 'updated'}`);
}

for (const { name, cfg } of routes) {
  const r = db.routes.updateOne({ 'ConfigJson.RouteId': cfg.RouteId },
    { $set: { Name: name, ConfigJson: cfg, Updated: now }, $setOnInsert: { Created: now } }, { upsert: true });
  out.routes.push(`${cfg.RouteId}: ${r.upsertedCount ? 'created' : 'updated'}`);
}

const salt = crypto.randomBytes(20);
const key = crypto.pbkdf2Sync(password, salt, 1000, 20, 'sha1');
const u = db.users.updateOne({ Username: username },
  {
    $set: { PasswordKey: bin(key), PasswordSalt: bin(salt), IsDisabled: false },
    $addToSet: { Scopes: { $each: scopes } },
    $setOnInsert: { IsAdmin: false }
  }, { upsert: true });
out.user = `${username}: ${u.upsertedCount ? 'created' : 'updated'}, scopes ${db.users.findOne({ Username: username }).Scopes.join(',')}`;

for (const k of ['YarpModificationToken', 'UsersModificationToken']) {
  db.Secrets.updateOne({ Key: k }, { $set: { Value: crypto.randomBytes(75).toString('base64') } }, { upsert: true });
}

printjson(out);
