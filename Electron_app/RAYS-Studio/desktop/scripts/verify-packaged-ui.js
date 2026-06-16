#!/usr/bin/env node
/**
 * Fail the build if the packaged app does not contain ui/dist/index.html.
 * Run after electron-builder (mac-arm64 output).
 */
const fs = require("node:fs");
const path = require("node:path");
const { execSync } = require("node:child_process");

const releaseDir = path.join(__dirname, "..", "release");
const macDirs = fs.existsSync(releaseDir)
  ? fs.readdirSync(releaseDir).filter((n) => n.startsWith("mac"))
  : [];

if (!macDirs.length) {
  console.error("verify-packaged-ui: no release/mac-* folder found under", releaseDir);
  process.exit(1);
}

const appRoot = path.join(releaseDir, macDirs[0]);
const apps = fs.readdirSync(appRoot).filter((n) => n.endsWith(".app"));
if (!apps.length) {
  console.error("verify-packaged-ui: no .app in", appRoot);
  process.exit(1);
}

const resources = path.join(appRoot, apps[0], "Contents", "Resources");
const asarPath = path.join(resources, "app.asar");
const unpackedIndex = path.join(resources, "ui", "dist", "index.html");

let ok = fs.existsSync(unpackedIndex);

if (!ok && fs.existsSync(asarPath)) {
  try {
    const listing = execSync(`npx --yes asar list "${asarPath}"`, { encoding: "utf8" });
    ok = listing.includes("ui/dist/index.html");
  } catch (err) {
    console.warn("verify-packaged-ui: could not read asar:", err.message);
  }
}

if (!ok) {
  console.error(
    "verify-packaged-ui: FAILED — ui/dist/index.html is missing from the built .app.\n" +
      "  Fix desktop/package.json build.files (use from/to for ../ui/dist)."
  );
  process.exit(1);
}

console.log("verify-packaged-ui: OK — ui/dist/index.html is in the app bundle");
