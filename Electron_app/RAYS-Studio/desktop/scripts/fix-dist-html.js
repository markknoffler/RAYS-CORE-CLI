const fs = require("node:fs");
const path = require("node:path");

const indexPath = path.resolve(__dirname, "../../ui/dist/index.html");
if (!fs.existsSync(indexPath)) {
  console.error(`Missing dist index: ${indexPath}`);
  process.exit(1);
}

const before = fs.readFileSync(indexPath, "utf8");
const after = before.replace(/\s+crossorigin(?=[\s>])/g, "");

if (before !== after) {
  fs.writeFileSync(indexPath, after, "utf8");
  console.log("Patched dist/index.html: removed crossorigin attrs for file:// Electron load.");
} else {
  console.log("dist/index.html already patched (no crossorigin attrs found).");
}
