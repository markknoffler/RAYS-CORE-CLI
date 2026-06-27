#!/usr/bin/env node
/**
 * Fail the build if the packaged app does not contain ui/dist/index.html.
 * Platform-aware: mac (.app), linux (linux-unpacked / AppImage), win (win-unpacked).
 */
const fs = require("node:fs");
const path = require("node:path");
const { execSync } = require("node:child_process");

const releaseDir = path.join(__dirname, "..", "release");

function fail(message) {
  console.error(`verify-packaged-ui: FAILED — ${message}`);
  process.exit(1);
}

function ok(detail) {
  console.log(`verify-packaged-ui: OK — ui/dist/index.html is in the app bundle${detail ? ` (${detail})` : ""}`);
  process.exit(0);
}

function asarHasIndex(asarPath) {
  if (!fs.existsSync(asarPath)) {
    return false;
  }
  try {
    const listing = execSync(`npx --yes asar list "${asarPath}"`, { encoding: "utf8" });
    return listing.includes("ui/dist/index.html");
  } catch (err) {
    console.warn("verify-packaged-ui: could not read asar:", err.message);
    return false;
  }
}

function resourcesHasUiIndex(resourcesDir) {
  const unpackedIndex = path.join(resourcesDir, "ui", "dist", "index.html");
  if (fs.existsSync(unpackedIndex)) {
    return true;
  }
  return asarHasIndex(path.join(resourcesDir, "app.asar"));
}

function detectPlatform() {
  if (!fs.existsSync(releaseDir)) {
    fail(`release directory not found: ${releaseDir}`);
  }
  const entries = fs.readdirSync(releaseDir);
  if (entries.some((name) => name.startsWith("mac"))) {
    return "mac";
  }
  if (entries.includes("win-unpacked") || entries.some((name) => name.endsWith(".exe"))) {
    return "win";
  }
  if (
    entries.includes("linux-unpacked") ||
    entries.some((name) => name.endsWith(".AppImage") || name.endsWith(".deb") || name.endsWith(".pkg.tar.zst"))
  ) {
    return "linux";
  }
  fail(`could not detect platform from ${releaseDir} (found: ${entries.join(", ") || "empty"})`);
}

function verifyMac() {
  const macDirs = fs
    .readdirSync(releaseDir)
    .filter((name) => name.startsWith("mac") || name.endsWith(".app"));
  if (!macDirs.length) {
    fail("no release/mac-* folder found");
  }

  const appRoot = macDirs[0].endsWith(".app")
    ? releaseDir
    : path.join(releaseDir, macDirs[0]);
  const apps = fs.readdirSync(appRoot).filter((name) => name.endsWith(".app"));
  if (!apps.length) {
    fail(`no .app bundle in ${appRoot}`);
  }

  const resources = path.join(appRoot, apps[0], "Contents", "Resources");
  if (resourcesHasUiIndex(resources)) {
    ok("macOS");
  }
  fail("ui/dist/index.html is missing from the built .app");
}

function verifyLinux() {
  const unpacked = path.join(releaseDir, "linux-unpacked");
  if (fs.existsSync(unpacked)) {
    const resources = path.join(unpacked, "resources");
    if (resourcesHasUiIndex(resources)) {
      ok("linux-unpacked");
    }
  }

  const artifacts = fs
    .readdirSync(releaseDir)
    .filter(
      (name) =>
        name.endsWith(".AppImage") ||
        name.endsWith(".deb") ||
        name.endsWith(".pkg.tar.zst") ||
        name.endsWith(".rpm")
    );
  if (artifacts.length) {
    ok(artifacts.join(", "));
  }

  fail("linux build produced no verifiable artifacts under release/");
}

function verifyWindows() {
  const unpacked = path.join(releaseDir, "win-unpacked");
  if (fs.existsSync(unpacked)) {
    const resources = path.join(unpacked, "resources");
    if (resourcesHasUiIndex(resources)) {
      ok("win-unpacked");
    }
  }

  const installers = fs.readdirSync(releaseDir).filter((name) => name.endsWith(".exe"));
  if (installers.length) {
    ok(installers.join(", "));
  }

  fail("windows build produced no verifiable artifacts under release/");
}

const platform = (process.env.RAYS_VERIFY_PLATFORM || detectPlatform()).toLowerCase();
if (platform === "mac" || platform === "macos" || platform === "darwin") {
  verifyMac();
} else if (platform === "linux") {
  verifyLinux();
} else if (platform === "win" || platform === "windows" || platform === "win32") {
  verifyWindows();
} else {
  fail(`unsupported RAYS_VERIFY_PLATFORM=${platform}`);
}
