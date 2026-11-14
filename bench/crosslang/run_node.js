// Prints one JSON report per line for each FILE, using the Node binding.
// Usage: node run_node.js <bindings/node dir> <anchors.pem|-> <prevalence|-> FILE...
const fs = require('node:fs');
const path = require('node:path');
const [dir, anchors, prevalenceArg, ...files] = process.argv.slice(2);
const isitai = require(path.resolve(dir, 'index.js'));
const trustAnchorsPem = anchors === '-' ? undefined : fs.readFileSync(anchors, 'utf8');
const prevalence = prevalenceArg === '-' ? undefined : Number(prevalenceArg);

(async () => {
  for (const f of files) {
    let report;
    try {
      report = await isitai.checkFile(f, { trustAnchorsPem, prevalence });
    } catch (e) {
      report = { error: e.message };
    }
    console.log(JSON.stringify({ file: path.basename(f), report }));
  }
})();
