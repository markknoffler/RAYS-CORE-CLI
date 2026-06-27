#!/usr/bin/env node
/**
 * Cross-platform entry for bundling the Python backend (bash on Unix, PowerShell on Windows).
 */
const { spawnSync } = require("node:child_process");
const path = require("node:path");

const scriptDir = __dirname;
const isWindows = process.platform === "win32";
const command = isWindows ? "powershell" : "bash";
const args = isWindows
  ? ["-ExecutionPolicy", "Bypass", "-File", path.join(scriptDir, "bundle-backend.ps1")]
  : [path.join(scriptDir, "bundle-backend.sh")];

const result = spawnSync(command, args, { stdio: "inherit", cwd: path.join(scriptDir, "..") });
if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}
process.exit(result.status ?? 1);
