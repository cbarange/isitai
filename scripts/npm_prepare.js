// Run in bindings/node after `napi create-npm-dirs` and `napi artifacts`.
// Points each platform package at the repo (required for npm provenance) and
// lists them as optionalDependencies of the main package, at the same version.
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const mainPath = path.resolve('package.json');
const main = JSON.parse(fs.readFileSync(mainPath, 'utf8'));
const optional = {};

for (const dir of fs.readdirSync('npm')) {
  const pkgPath = path.join('npm', dir, 'package.json');
  const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
  const binaries = fs.readdirSync(path.join('npm', dir)).filter((f) => f.endsWith('.node'));
  if (binaries.length !== 1) throw new Error(`${pkg.name}: expected one .node file, found ${binaries.length}`);
  pkg.version = main.version;
  pkg.license = main.license;
  pkg.repository = main.repository;
  pkg.publishConfig = { access: 'public' };
  fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n');
  optional[pkg.name] = main.version;
}

main.optionalDependencies = optional;
fs.writeFileSync(mainPath, JSON.stringify(main, null, 2) + '\n');
console.log(`prepared ${Object.keys(optional).length} platform packages:`, Object.keys(optional).join(', '));
