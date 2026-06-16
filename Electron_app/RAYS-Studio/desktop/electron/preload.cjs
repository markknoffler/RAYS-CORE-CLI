const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("raysDesktop", {
  isElectron: true,
  getInstallEpoch: () => ipcRenderer.invoke("rays:get-install-epoch"),
  selectFolder: () => ipcRenderer.invoke("rays:select-folder"),
  readFile: (workspaceRoot, relativePath) =>
    ipcRenderer.invoke("rays:read-file", { workspaceRoot, relativePath }),
  startSession: (workspacePath, runtimeOverrides, conversationId) =>
    ipcRenderer.invoke("rays:session-start", { workspacePath, runtimeOverrides, conversationId }),
  stopSession: (sessionId) => ipcRenderer.invoke("rays:session-stop", { sessionId }),
  readMcpConfig: (scope, workspaceRoot) =>
    ipcRenderer.invoke("rays:read-mcp-config", { scope, workspaceRoot }),
  writeMcpConfig: (scope, workspaceRoot, server) =>
    ipcRenderer.invoke("rays:write-mcp-config", { scope, workspaceRoot, server }),
  removeMcpServer: (scope, workspaceRoot, name) =>
    ipcRenderer.invoke("rays:remove-mcp-server", { scope, workspaceRoot, name }),
  loadMcpExample: () => ipcRenderer.invoke("rays:load-mcp-example"),
  selectSkillFolder: () => ipcRenderer.invoke("rays:select-skill-folder"),
  installSkill: (scope, workspaceRoot, sourceDir) =>
    ipcRenderer.invoke("rays:install-skill", { scope, workspaceRoot, sourceDir }),
  listSkills: (workspaceRoot) => ipcRenderer.invoke("rays:list-skills", { workspaceRoot }),
  openSkillsDirectory: (scope, workspaceRoot) =>
    ipcRenderer.invoke("rays:open-skills-directory", { scope, workspaceRoot }),
  onMenuAction: (callback) => {
    const listener = (_event, payload) => callback(payload?.action, payload);
    ipcRenderer.on("rays:menu-action", listener);
    return () => ipcRenderer.removeListener("rays:menu-action", listener);
  },
});
