const { app, BrowserWindow, ipcMain, dialog, Menu, nativeImage, shell, session } = require("electron");
const path = require("node:path");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const os = require("node:os");
const { spawn, execSync } = require("node:child_process");
const { randomUUID } = require("node:crypto");
const { pathToFileURL } = require("node:url");

const isDev = !app.isPackaged;
const STUDIO_DEV_URL = process.env.RAYS_STUDIO_URL || "http://127.0.0.1:8080";

function readBundledInstallEpoch() {
  try {
    const epochPath = path.join(__dirname, "install-epoch.json");
    if (fs.existsSync(epochPath)) {
      const parsed = JSON.parse(fs.readFileSync(epochPath, "utf8"));
      if (parsed && parsed.epoch) return String(parsed.epoch);
    }
  } catch (err) {
    console.warn("Could not read install-epoch.json:", err);
  }
  return isDev ? "dev" : app.getVersion();
}

async function ensureFreshUserData(installEpoch) {
  const markerPath = path.join(app.getPath("userData"), "install-epoch.txt");
  let stored = "";
  try {
    stored = fs.readFileSync(markerPath, "utf8").trim();
  } catch {
    // first launch or missing marker
  }
  if (stored === installEpoch) return;
  const defaultSession = session.defaultSession;
  await defaultSession.clearStorageData();
  await defaultSession.clearCache();
  await fsp.mkdir(path.dirname(markerPath), { recursive: true });
  await fsp.writeFile(markerPath, installEpoch, "utf8");
  console.log("RAYS Studio: reset persisted storage for install epoch", installEpoch);
}

/** @type {Map<string, import('node:child_process').ChildProcessWithoutNullStreams>} */
const bridgeSessions = new Map();

/** @type {BrowserWindow | null} */
let mainWindow = null;

function sendToRenderer(channel, payload) {
  const win = BrowserWindow.getFocusedWindow() || mainWindow;
  if (win && !win.isDestroyed()) {
    win.webContents.send(channel, payload);
  }
}

function appIconPath() {
  const buildIcon = path.join(__dirname, "../build/icon.png");
  if (fs.existsSync(buildIcon)) return buildIcon;
  return undefined;
}

function mcpConfigPath(scope, workspaceRoot) {
  if (scope === "project") {
    if (!workspaceRoot) throw new Error("workspaceRoot is required for project MCP config");
    return path.join(workspaceRoot, ".rays", "mcp.json");
  }
  return path.join(os.homedir(), ".rays", "mcp.json");
}

async function readMcpJson(scope, workspaceRoot) {
  const filePath = mcpConfigPath(scope, workspaceRoot);
  if (!fs.existsSync(filePath)) return { mcp_servers: [] };
  const raw = await fsp.readFile(filePath, "utf8");
  const parsed = JSON.parse(raw);
  if (Array.isArray(parsed)) return { mcp_servers: parsed };
  return { mcp_servers: parsed.mcp_servers || [] };
}

async function writeMcpJson(scope, workspaceRoot, servers) {
  const filePath = mcpConfigPath(scope, workspaceRoot);
  await fsp.mkdir(path.dirname(filePath), { recursive: true });
  await fsp.writeFile(filePath, JSON.stringify({ mcp_servers: servers }, null, 2), "utf8");
}

function shellPathEnv() {
  const home = os.homedir();
  const extra = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
    path.join(home, ".local/bin"),
    path.join(home, ".cargo/bin"),
  ];
  const parts = (process.env.PATH || "").split(path.delimiter).filter(Boolean);
  for (const entry of extra) {
    if (!parts.includes(entry)) parts.unshift(entry);
  }
  return parts.join(path.delimiter);
}

function resolveExecutable(command) {
  const cmd = String(command || "").trim();
  if (!cmd || cmd.includes("/") || cmd.includes("\\")) return cmd;
  try {
    const resolved = execSync(`command -v ${cmd}`, {
      encoding: "utf8",
      env: { ...process.env, PATH: shellPathEnv() },
    }).trim();
    if (resolved) return resolved;
  } catch {
    // fall through to common install locations
  }
  const home = os.homedir();
  const candidates = [
    `/opt/homebrew/bin/${cmd}`,
    `/usr/local/bin/${cmd}`,
    path.join(home, ".local/bin", cmd),
    path.join(home, ".cargo/bin", cmd),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return cmd;
}

function normalizeMcpServer(server) {
  const normalized = { ...server };
  if (normalized.command) {
    normalized.command = resolveExecutable(normalized.command);
  }
  if (String(normalized.name || "").toLowerCase() === "blender") {
    normalized.env = {
      BLENDER_HOST: "localhost",
      BLENDER_PORT: "9876",
      DISABLE_TELEMETRY: "true",
      UV_PYTHON_PREFERENCE: "only-managed",
      ...(normalized.env || {}),
    };
    if (normalized.quiet === undefined) normalized.quiet = false;
    if (normalized.enabled === undefined) normalized.enabled = true;
  }
  return normalized;
}

async function copyDirRecursive(src, dest) {
  await fsp.mkdir(dest, { recursive: true });
  const entries = await fsp.readdir(src, { withFileTypes: true });
  for (const entry of entries) {
    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      await copyDirRecursive(from, to);
    } else {
      await fsp.copyFile(from, to);
    }
  }
}

function skillsRoot(scope, workspaceRoot) {
  if (scope === "project") {
    if (!workspaceRoot) throw new Error("workspaceRoot is required for project skills");
    return path.join(workspaceRoot, "skills");
  }
  return path.join(os.homedir(), ".rays", "skills");
}

async function listSkillsForWorkspace(workspaceRoot) {
  const results = [];
  const scopes = [
    ["project", workspaceRoot ? path.join(workspaceRoot, "skills") : null],
    ["global", path.join(os.homedir(), ".rays", "skills")],
  ];
  for (const [scope, root] of scopes) {
    if (!root || !fs.existsSync(root)) continue;
    const names = await fsp.readdir(root);
    for (const name of names) {
      const skillDir = path.join(root, name);
      const stat = await fsp.stat(skillDir);
      if (!stat.isDirectory()) continue;
      const skillMd = path.join(skillDir, "SKILL.md");
      if (!fs.existsSync(skillMd)) continue;
      results.push({ name, scope, path: skillDir });
    }
  }
  return results;
}

function buildApplicationMenu() {
  const isMac = process.platform === "darwin";
  const template = [
    ...(isMac
      ? [
          {
            label: app.name,
            submenu: [
              { role: "about" },
              { type: "separator" },
              {
                label: "New Agent Window",
                accelerator: "CmdOrCtrl+Shift+A",
                click: () => createWindow({ hash: "/agent" }),
              },
              {
                label: "New IDE Window",
                accelerator: "CmdOrCtrl+Shift+I",
                click: () => createWindow({ hash: "/ide" }),
              },
              { type: "separator" },
              { role: "services" },
              { type: "separator" },
              { role: "hide" },
              { role: "hideOthers" },
              { role: "unhide" },
              { type: "separator" },
              { role: "quit" },
            ],
          },
        ]
      : []),
    {
      label: "File",
      submenu: [
        {
          label: "Open Folder…",
          accelerator: "CmdOrCtrl+O",
          click: () => sendToRenderer("rays:menu-action", { action: "open-folder" }),
        },
        {
          label: "Open Recent",
          submenu: [
            {
              label: "Choose from list…",
              click: () => sendToRenderer("rays:menu-action", { action: "show-launcher" }),
            },
          ],
        },
        { type: "separator" },
        {
          label: "New Agent Window",
          accelerator: "CmdOrCtrl+Shift+A",
          click: () => createWindow({ hash: "/agent" }),
        },
        {
          label: "New IDE Window",
          accelerator: "CmdOrCtrl+Shift+I",
          click: () => createWindow({ hash: "/ide" }),
        },
        {
          label: "Close Workspace",
          accelerator: "CmdOrCtrl+W",
          click: () => sendToRenderer("rays:menu-action", { action: "close-workspace" }),
        },
        ...(!isMac ? [{ type: "separator" }, { role: "quit" }] : []),
      ],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [
        {
          label: "Agent",
          accelerator: "CmdOrCtrl+1",
          click: () => sendToRenderer("rays:menu-action", { action: "navigate-agent" }),
        },
        {
          label: "IDE",
          accelerator: "CmdOrCtrl+2",
          click: () => sendToRenderer("rays:menu-action", { action: "navigate-ide" }),
        },
        { type: "separator" },
        { role: "reload" },
        { role: "forceReload" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
      ],
    },
    {
      label: "Window",
      submenu: [{ role: "minimize" }, { role: "zoom" }, ...(isMac ? [{ type: "separator" }, { role: "front" }] : [{ role: "close" }])],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function pythonCommand() {
  return process.platform === "win32" ? "python" : "python3";
}

function repoRoot() {
  return path.resolve(__dirname, "../..");
}

function bundledBridgeBinary() {
  const name = process.platform === "win32" ? "rays-gui-bridge.exe" : "rays-gui-bridge";
  return path.join(process.resourcesPath, "backend", name);
}

function bridgeLaunchConfig() {
  // Packaged app: self-contained backend (PyInstaller), no pipx / system Python required.
  if (app.isPackaged) {
    const binary = bundledBridgeBinary();
    if (!fs.existsSync(binary)) {
      console.warn(
        `RAYS backend missing in app bundle (${binary}). Rebuild with: npm run bundle:backend`
      );
    }
    return {
      command: binary,
      argsPrefix: [],
      cwd: process.env.HOME || process.cwd(),
      env: { ...process.env, PATH: shellPathEnv(), PYTHONUNBUFFERED: "1" },
    };
  }

  // Development: use repo source + local Python
  const root = repoRoot();
  return {
    command: pythonCommand(),
    argsPrefix: ["-m", "rays_bridge.ws_bridge"],
    cwd: root,
    env: {
      ...process.env,
      PATH: shellPathEnv(),
      PYTHONPATH: [
        path.join(root, "src"),
        path.join(root, "bridge/src"),
        process.env.PYTHONPATH || "",
      ]
        .filter(Boolean)
        .join(path.delimiter),
    },
  };
}

function resolvePackagedStudioIndex() {
  const candidates = [
    path.join(app.getAppPath(), "ui/dist/index.html"),
    path.join(process.resourcesPath, "ui/dist/index.html"),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

function missingUiErrorHtml(searched) {
  const lines = searched.map((p) => `<li><code>${p}</code></li>`).join("");
  return `data:text/html;charset=utf-8,${encodeURIComponent(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>RAYS Studio — UI missing</title>
<style>body{font-family:system-ui,sans-serif;max-width:42rem;margin:3rem auto;padding:0 1rem;line-height:1.5}
h1{color:#c00}code{font-size:0.9em;background:#f4f4f4;padding:0.1em 0.3em}</style></head>
<body><h1>RAYS Studio UI was not packaged</h1>
<p>The app window is blank because <code>ui/dist/index.html</code> is not inside the installed app.</p>
<p>Reinstall from a DMG built after the packaging fix, or run from source:</p>
<pre>cd RAYS-Studio/desktop && npm run dev</pre>
<p>Searched:</p><ul>${lines}</ul></body></html>`)}`;
}

function createWindow(options = {}) {
  const devUrl = STUDIO_DEV_URL;
  const routeHash = String(options.hash || process.env.RAYS_INITIAL_ROUTE || "").replace(/^#?\/?/, "");
  const hashSuffix = routeHash ? `#/${routeHash.replace(/^\//, "")}` : "";
  let studioLoadTarget = `${devUrl}${hashSuffix}`;

  if (!isDev) {
    const indexPath = resolvePackagedStudioIndex();
    if (indexPath) {
      console.log("Loading RAYS Studio from:", indexPath);
      studioLoadTarget = `${pathToFileURL(indexPath).href}${hashSuffix}`;
    } else {
      const searched = [
        path.join(app.getAppPath(), "ui/dist/index.html"),
        path.join(process.resourcesPath, "ui/dist/index.html"),
      ];
      console.error("RAYS Studio UI missing. Searched:", searched);
      studioLoadTarget = missingUiErrorHtml(searched);
    }
  }

  const iconPath = appIconPath();
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    title: "RAYS Studio",
    icon: iconPath ? nativeImage.createFromPath(iconPath) : undefined,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
    },
  });

  win.webContents.on("did-fail-load", (event, errorCode, errorDescription, validatedURL) => {
    console.error(`Failed to load URL: ${validatedURL}`);
    console.error(`Error code: ${errorCode} (${errorDescription})`);
  });
  win.webContents.on("console-message", (_event, level, message) => {
    console.log(`[renderer:${level}] ${message}`);
  });
  win.webContents.on("render-process-gone", (_event, details) => {
    console.error("Renderer process gone:", details);
  });

  if (isDev) {
    console.log("Loading RAYS Studio in dev mode from:", studioLoadTarget);
    win.loadURL(studioLoadTarget);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadURL(studioLoadTarget).catch((err) => {
      console.error("Failed to load RAYS Studio UI:", studioLoadTarget, err);
    });
    if (process.env.RAYS_STUDIO_DEBUG === "1") {
      win.webContents.openDevTools({ mode: "detach" });
    }
  }

  mainWindow = win;
  return win;
}

app.whenReady().then(async () => {
  const installEpoch = readBundledInstallEpoch();
  await ensureFreshUserData(installEpoch);
  buildApplicationMenu();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  for (const child of bridgeSessions.values()) {
    child.kill("SIGTERM");
  }
  bridgeSessions.clear();
  if (process.platform !== "darwin") app.quit();
});

ipcMain.handle("rays:get-install-epoch", () => ({ epoch: readBundledInstallEpoch() }));

ipcMain.handle("rays:select-folder", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory", "createDirectory"],
  });
  if (result.canceled || !result.filePaths.length) return { path: null };
  return { path: result.filePaths[0] };
});

ipcMain.handle("rays:read-file", async (_event, { workspaceRoot, relativePath }) => {
  const normalizedRoot = path.resolve(workspaceRoot);
  const resolvedPath = path.resolve(normalizedRoot, relativePath);
  if (!resolvedPath.startsWith(normalizedRoot)) {
    throw new Error("Invalid file path");
  }
  const content = await fsp.readFile(resolvedPath, "utf8");
  return { content };
});

ipcMain.handle("rays:session-start", async (_event, { workspacePath, runtimeOverrides, conversationId }) => {
  if (!workspacePath) throw new Error("workspacePath is required");

  const sessionId = randomUUID();
  const launch = bridgeLaunchConfig();
  const bridgeArgs = [
    ...launch.argsPrefix,
    "--workspace",
    workspacePath,
    "--port",
    "0",
    "--runtime_overrides",
    JSON.stringify(runtimeOverrides || {}),
  ];
  if (conversationId) {
    bridgeArgs.push("--conversation_id", String(conversationId));
  }
  const child = spawn(
    launch.command,
    bridgeArgs,
    {
      cwd: launch.cwd,
      env: launch.env,
    }
  );

  return await new Promise((resolve, reject) => {
    let settled = false;
    let stderrTail = "";
    const timeout = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill("SIGTERM");
      const detail = stderrTail ? ` Last error: ${stderrTail.slice(-400)}` : "";
      reject(new Error(`RAYS backend did not start within 2 minutes.${detail}`));
    }, 120000);

    const onFail = (message) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      const detail = stderrTail ? ` ${stderrTail.slice(-400)}` : "";
      reject(new Error(`${message}${detail}`));
    };

    child.stderr.on("data", (chunk) => {
      const text = chunk.toString("utf8");
      stderrTail = (stderrTail + text).slice(-8000);
      const trimmed = text.trim();
      if (trimmed) console.warn("[rays-bridge stderr]", trimmed);
    });

    const handleBridgeLine = (line) => {
      if (!line.trim()) return;
      try {
        const parsed = JSON.parse(line);
        if (parsed.event === "bridge_ready" && typeof parsed.port === "number") {
          if (settled) return;
          settled = true;
          clearTimeout(timeout);
          bridgeSessions.set(sessionId, child);
          resolve({ sessionId, wsPort: parsed.port });
          return;
        }
        if (parsed.event === "bridge_fatal" || parsed.event === "bridge_init_failed") {
          onFail(parsed.message || "RAYS backend failed to start");
        }
      } catch {
        // ignore non-json
      }
    };

    child.stdout.on("data", (chunk) => {
      const lines = chunk.toString("utf8").split("\n");
      for (const line of lines) {
        handleBridgeLine(line);
      }
    });

    child.on("error", (err) => onFail(err.message));
    child.on("exit", (code) => {
      if (!settled) {
        onFail(`RAYS backend exited before it was ready (code: ${code ?? "unknown"})`);
      }
    });
  });
});

ipcMain.handle("rays:session-stop", async (_event, { sessionId }) => {
  const child = bridgeSessions.get(sessionId);
  if (!child) return { stopped: false };
  child.kill("SIGTERM");
  bridgeSessions.delete(sessionId);
  return { stopped: true };
});

ipcMain.handle("rays:read-mcp-config", async (_event, { scope, workspaceRoot }) => {
  return readMcpJson(scope, workspaceRoot || null);
});

ipcMain.handle("rays:write-mcp-config", async (_event, { scope, workspaceRoot, server }) => {
  const current = await readMcpJson(scope, workspaceRoot || null);
  const normalized = normalizeMcpServer(server);
  const servers = (current.mcp_servers || []).filter((entry) => entry.name !== normalized.name);
  servers.push(normalized);
  await writeMcpJson(scope, workspaceRoot || null, servers);
  return { ok: true, server: normalized };
});

ipcMain.handle("rays:remove-mcp-server", async (_event, { scope, workspaceRoot, name }) => {
  const current = await readMcpJson(scope, workspaceRoot || null);
  const servers = (current.mcp_servers || []).filter((entry) => entry.name !== name);
  await writeMcpJson(scope, workspaceRoot || null, servers);
  return { ok: true };
});

ipcMain.handle("rays:load-mcp-example", async () => {
  const MCP_EXAMPLE_FALLBACK = {
    mcp_servers: [
      {
        name: "blender",
        description:
          "Enables prompt-assisted 3D modeling, scene creation, and manipulation in Blender via Python code execution.",
        command: "uvx",
        args: ["--python", "3.11", "blender-mcp"],
        env: {
          BLENDER_HOST: "localhost",
          BLENDER_PORT: "9876",
          DISABLE_TELEMETRY: "true",
          UV_PYTHON_PREFERENCE: "only-managed",
        },
        enabled: true,
        quiet: false,
      },
    ],
  };

  const candidates = [
    path.join(app.getAppPath(), "ui/dist/examples/mcp-blender.json"),
    path.join(process.resourcesPath, "ui/dist/examples/mcp-blender.json"),
    path.join(repoRoot(), "ui/dist/examples/mcp-blender.json"),
    path.join(repoRoot(), "ui/public/examples/mcp-blender.json"),
  ];

  for (const examplePath of candidates) {
    if (fs.existsSync(examplePath)) {
      const raw = await fsp.readFile(examplePath, "utf8");
      return JSON.parse(raw);
    }
  }

  return MCP_EXAMPLE_FALLBACK;
});

ipcMain.handle("rays:select-skill-folder", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory"],
    title: "Choose skill folder (must contain SKILL.md)",
  });
  if (result.canceled || !result.filePaths.length) return { path: null };
  return { path: result.filePaths[0] };
});

ipcMain.handle("rays:open-skills-directory", async (_event, { scope, workspaceRoot }) => {
  const root = skillsRoot(scope, workspaceRoot || null);
  await fsp.mkdir(root, { recursive: true });
  const err = await shell.openPath(root);
  if (err) throw new Error(err);
  return { path: root };
});

ipcMain.handle("rays:install-skill", async (_event, { scope, workspaceRoot, sourceDir }) => {
  const skillMd = path.join(sourceDir, "SKILL.md");
  if (!fs.existsSync(skillMd)) {
    throw new Error("SKILL.md not found in selected folder");
  }
  const skillName = path.basename(sourceDir);
  const targetRoot = path.join(skillsRoot(scope, workspaceRoot || null), skillName);
  if (fs.existsSync(targetRoot)) {
    throw new Error(`Skill "${skillName}" already exists in ${scope} scope`);
  }
  await copyDirRecursive(sourceDir, targetRoot);
  return { ok: true, targetPath: targetRoot };
});

ipcMain.handle("rays:list-skills", async (_event, { workspaceRoot }) => {
  return listSkillsForWorkspace(workspaceRoot || null);
});
