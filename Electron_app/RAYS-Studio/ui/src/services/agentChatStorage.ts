import type { AgentTurn } from "./agentActivity";

const PREFIX = "rays-studio:agent-chat:";

export function loadAgentChatTurns(sessionId: string): AgentTurn[] {
  if (!sessionId) return [];
  try {
    const raw = localStorage.getItem(`${PREFIX}${sessionId}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as AgentTurn[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveAgentChatTurns(sessionId: string, turns: AgentTurn[]) {
  if (!sessionId) return;
  try {
    localStorage.setItem(`${PREFIX}${sessionId}`, JSON.stringify(turns));
  } catch {
    // ignore quota errors
  }
}

export function removeAgentChatTurns(sessionId: string) {
  localStorage.removeItem(`${PREFIX}${sessionId}`);
}
