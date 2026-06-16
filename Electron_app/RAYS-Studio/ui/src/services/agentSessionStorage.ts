export type AgentSession = {
  id: string;
  workspacePath: string;
  title: string;
  updatedAt: number;
  /** When true (default), first AI response may replace the placeholder title. */
  autoTitle?: boolean;
};

const STORAGE_KEY = "rays-studio:agent-sessions";

function loadAll(): AgentSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as AgentSession[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveAll(sessions: AgentSession[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  window.dispatchEvent(new CustomEvent("rays-agent-sessions-changed"));
}

export function listAgentSessions(): AgentSession[] {
  return loadAll().sort((a, b) => b.updatedAt - a.updatedAt);
}

export function sessionsByWorkspace(): Record<string, AgentSession[]> {
  const grouped: Record<string, AgentSession[]> = {};
  for (const session of listAgentSessions()) {
    if (!grouped[session.workspacePath]) grouped[session.workspacePath] = [];
    grouped[session.workspacePath].push(session);
  }
  for (const path of Object.keys(grouped)) {
    grouped[path].sort((a, b) => b.updatedAt - a.updatedAt);
  }
  return grouped;
}

export function ensureAgentSession(
  workspacePath: string,
  id: string,
  title?: string
): AgentSession {
  const sessions = loadAll();
  const existing = sessions.find((s) => s.id === id);
  if (existing) {
    return existing;
  }
  const session: AgentSession = {
    id,
    workspacePath,
    title: title || defaultTitle(workspacePath),
    updatedAt: Date.now(),
    autoTitle: true,
  };
  saveAll([session, ...sessions]);
  return session;
}

export function createAgentSession(workspacePath: string, title?: string): AgentSession {
  const session: AgentSession = {
    id: crypto.randomUUID(),
    workspacePath,
    title: title || defaultTitle(workspacePath),
    updatedAt: Date.now(),
    autoTitle: true,
  };
  const next = [session, ...loadAll()];
  saveAll(next);
  return session;
}

export function bumpAgentSession(id: string) {
  const sessions = loadAll();
  const idx = sessions.findIndex((s) => s.id === id);
  if (idx < 0) return;
  sessions[idx] = {
    ...sessions[idx],
    updatedAt: Date.now(),
  };
  saveAll(sessions);
}

export function touchAgentSession(id: string, title?: string) {
  const sessions = loadAll();
  const idx = sessions.findIndex((s) => s.id === id);
  if (idx < 0) return;
  sessions[idx] = {
    ...sessions[idx],
    updatedAt: Date.now(),
    title: title || sessions[idx].title,
  };
  saveAll(sessions);
}

export function setAgentSessionTitle(id: string, title: string) {
  const trimmed = title.trim().slice(0, 80);
  if (!trimmed) return;
  const sessions = loadAll();
  const idx = sessions.findIndex((s) => s.id === id);
  if (idx < 0) return;
  const session = sessions[idx];
  if (session.autoTitle === false) return;
  sessions[idx] = {
    ...session,
    title: trimmed,
    autoTitle: false,
    updatedAt: Date.now(),
  };
  saveAll(sessions);
}

export function renameAgentSession(id: string, title: string) {
  const trimmed = title.trim().slice(0, 80);
  if (!trimmed) return;
  const sessions = loadAll();
  const idx = sessions.findIndex((s) => s.id === id);
  if (idx < 0) return;
  sessions[idx] = {
    ...sessions[idx],
    title: trimmed,
    autoTitle: false,
    updatedAt: Date.now(),
  };
  saveAll(sessions);
}

export function removeAgentSession(id: string) {
  saveAll(loadAll().filter((s) => s.id !== id));
}

function defaultTitle(workspacePath: string): string {
  const parts = workspacePath.replace(/\\/g, "/").split("/").filter(Boolean);
  const folder = parts[parts.length - 1] || "Workspace";
  const stamp = new Date().toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${folder} · ${stamp}`;
}

export function workspaceLabel(workspacePath: string): string {
  const parts = workspacePath.replace(/\\/g, "/").split("/").filter(Boolean);
  return parts[parts.length - 1] || workspacePath;
}
