import { useEffect, useState } from "react";
import {
  listAgentSessions,
  sessionsByWorkspace,
  type AgentSession,
} from "@/services/agentSessionStorage";

export function useAgentSessions() {
  const [sessions, setSessions] = useState<AgentSession[]>(() => listAgentSessions());
  const [grouped, setGrouped] = useState<Record<string, AgentSession[]>>(() => sessionsByWorkspace());

  useEffect(() => {
    const refresh = () => {
      setSessions(listAgentSessions());
      setGrouped(sessionsByWorkspace());
    };
    window.addEventListener("rays-agent-sessions-changed", refresh);
    window.addEventListener("storage", refresh);
    refresh();
    return () => {
      window.removeEventListener("rays-agent-sessions-changed", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  return { sessions, grouped };
}
