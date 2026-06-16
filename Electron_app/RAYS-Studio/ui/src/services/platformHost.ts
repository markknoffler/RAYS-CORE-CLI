import type { ProviderConfig } from "./raysSession";

export type SessionStartResult = { sessionId: string; wsPort: number };

export type McpConfigFile = {
  mcp_servers: Array<Record<string, unknown>>;
};

export type SkillEntry = {
  name: string;
  scope: "global" | "project";
  path: string;
  description?: string;
};

declare global {
  interface Window {
    raysDesktop?: {
      isElectron: boolean;
      getInstallEpoch: () => Promise<{ epoch: string }>;
      selectFolder: () => Promise<{ path: string | null }>;
      readFile: (workspaceRoot: string, relativePath: string) => Promise<{ content: string }>;
      startSession: (
        workspacePath: string,
        runtimeOverrides: Record<string, unknown>,
        conversationId?: string
      ) => Promise<SessionStartResult>;
      onMenuAction: (callback: (action: string, payload?: { path?: string }) => void) => () => void;
      stopSession: (sessionId: string) => Promise<{ stopped: boolean }>;
      readMcpConfig: (scope: "global" | "project", workspaceRoot?: string) => Promise<McpConfigFile>;
      writeMcpConfig: (
        scope: "global" | "project",
        workspaceRoot: string | undefined,
        server: Record<string, unknown>
      ) => Promise<{ ok: boolean }>;
      removeMcpServer: (
        scope: "global" | "project",
        workspaceRoot: string | undefined,
        name: string
      ) => Promise<{ ok: boolean }>;
      loadMcpExample: () => Promise<McpConfigFile>;
      selectSkillFolder: () => Promise<{ path: string | null }>;
      installSkill: (
        scope: "global" | "project",
        workspaceRoot: string | undefined,
        sourceDir: string
      ) => Promise<{ ok: boolean; targetPath: string }>;
      listSkills: (workspaceRoot?: string) => Promise<SkillEntry[]>;
      openSkillsDirectory: (
        scope: "global" | "project",
        workspaceRoot?: string
      ) => Promise<{ path: string }>;
    };
  }
}

function runtimeOverridesFromProvider(providerConfig: ProviderConfig) {
  const llm: Record<string, string> = {
    provider: providerConfig.provider,
    model: providerConfig.model,
    api_key: providerConfig.apiKey || "",
  };
  if (providerConfig.provider === "ollama") {
    llm.ollama_endpoint = "http://localhost:11434/api/generate";
  }
  return { llm };
}

export function isElectronHost(): boolean {
  return Boolean(window.raysDesktop?.isElectron);
}

export async function hostSelectFolder(): Promise<string> {
  if (window.raysDesktop) {
    const result = await window.raysDesktop.selectFolder();
    return result.path || "";
  }
  const response = await fetch("/api/system/select-folder", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error((await response.json()).error || "Failed to open folder picker");
  }
  const data = await response.json();
  return String(data.folderPath || "");
}

export async function hostStartSession(
  workspacePath: string,
  providerConfig: ProviderConfig,
  conversationId?: string
): Promise<SessionStartResult> {
  const runtimeOverrides = runtimeOverridesFromProvider(providerConfig);
  if (window.raysDesktop) {
    return window.raysDesktop.startSession(workspacePath, runtimeOverrides, conversationId);
  }
  const response = await fetch("/api/session/start", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ workspacePath, runtimeOverrides, conversationId }),
  });
  if (!response.ok) {
    throw new Error((await response.json()).error || "Failed to start session");
  }
  return response.json();
}

export async function hostStopSession(sessionId: string): Promise<void> {
  if (window.raysDesktop) {
    await window.raysDesktop.stopSession(sessionId);
    return;
  }
  await fetch("/api/session/stop", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ sessionId }),
  });
}

export async function hostReadFile(workspaceRoot: string, relativePath: string): Promise<string> {
  if (window.raysDesktop) {
    const data = await window.raysDesktop.readFile(workspaceRoot, relativePath);
    return String(data.content || "");
  }
  const response = await fetch("/api/file/read", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ workspaceRoot, relativePath }),
  });
  if (!response.ok) {
    throw new Error((await response.json()).error || "Failed to read file");
  }
  const data = await response.json();
  return String(data.content || "");
}

export async function hostReadMcpConfig(
  scope: "global" | "project",
  workspaceRoot?: string
): Promise<McpConfigFile> {
  if (window.raysDesktop) {
    return window.raysDesktop.readMcpConfig(scope, workspaceRoot);
  }
  return { mcp_servers: [] };
}

export async function hostWriteMcpConfig(
  scope: "global" | "project",
  workspaceRoot: string | undefined,
  server: Record<string, unknown>
): Promise<void> {
  if (!window.raysDesktop) throw new Error("MCP management requires the desktop app");
  await window.raysDesktop.writeMcpConfig(scope, workspaceRoot, server);
}

export async function hostRemoveMcpServer(
  scope: "global" | "project",
  workspaceRoot: string | undefined,
  name: string
): Promise<void> {
  if (!window.raysDesktop) throw new Error("MCP management requires the desktop app");
  await window.raysDesktop.removeMcpServer(scope, workspaceRoot, name);
}

export async function hostLoadMcpExample(): Promise<McpConfigFile> {
  if (window.raysDesktop) {
    return window.raysDesktop.loadMcpExample();
  }
  try {
    const response = await fetch("/examples/mcp-blender.json");
    if (response.ok) return response.json();
  } catch {
    // fall through to embedded example
  }
  const { MCP_BLENDER_EXAMPLE } = await import("@/data/mcpExample");
  return MCP_BLENDER_EXAMPLE;
}

export async function hostSelectSkillFolder(): Promise<string> {
  if (window.raysDesktop) {
    const result = await window.raysDesktop.selectSkillFolder();
    return result.path || "";
  }
  return "";
}

export async function hostInstallSkill(
  scope: "global" | "project",
  workspaceRoot: string | undefined,
  sourceDir: string
): Promise<void> {
  if (!window.raysDesktop) throw new Error("Skill install requires the desktop app");
  await window.raysDesktop.installSkill(scope, workspaceRoot, sourceDir);
}

export async function hostListSkills(workspaceRoot?: string): Promise<SkillEntry[]> {
  if (window.raysDesktop) {
    return window.raysDesktop.listSkills(workspaceRoot);
  }
  return [];
}

export async function hostOpenSkillsDirectory(
  scope: "global" | "project",
  workspaceRoot?: string
): Promise<string> {
  if (!window.raysDesktop) throw new Error("Skill folders require the desktop app");
  const result = await window.raysDesktop.openSkillsDirectory(scope, workspaceRoot);
  return result.path;
}
