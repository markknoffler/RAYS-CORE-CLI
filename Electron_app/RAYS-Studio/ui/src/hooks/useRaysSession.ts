import { useEffect, useState } from "react";
import { raysSessionStore, type SessionState } from "@/services/raysSession";

export function useRaysSession() {
  const [state, setState] = useState<SessionState>({
    sessionId: null,
    wsPort: null,
    connected: false,
    status: "disconnected",
    workspaceRoot: null,
    conversationId: null,
    fileTree: [],
    diffChunks: [],
    chatMessages: [],
    terminalLines: [],
    error: null,
    fileContents: {},
    hudPhase: "",
    hudDetail: "",
    tokenCount: 0,
    pendingApproval: null,
    executionMode: "autonomous",
    thinkingPhase: "hidden",
    thinkingText: "",
    turns: [],
  });

  useEffect(() => raysSessionStore.subscribe(setState), []);

  return {
    state,
    startSession: raysSessionStore.startSession.bind(raysSessionStore),
    switchSession: raysSessionStore.switchSession.bind(raysSessionStore),
    stopSession: raysSessionStore.stopSession.bind(raysSessionStore),
    submitPrompt: raysSessionStore.submitPrompt.bind(raysSessionStore),
    respondApproval: raysSessionStore.respondApproval.bind(raysSessionStore),
    setExecutionMode: raysSessionStore.setExecutionMode.bind(raysSessionStore),
    listMcpStatus: raysSessionStore.listMcpStatus.bind(raysSessionStore),
    reloadMcp: raysSessionStore.reloadMcp.bind(raysSessionStore),
    refreshTree: raysSessionStore.refreshTree.bind(raysSessionStore),
    sendTerminalInput: raysSessionStore.sendTerminalInput.bind(raysSessionStore),
    cancelCurrentTask: raysSessionStore.cancelCurrentTask.bind(raysSessionStore),
    selectFolder: raysSessionStore.selectFolder.bind(raysSessionStore),
    readFile: raysSessionStore.readFile.bind(raysSessionStore),
    completeThinkingReveal: raysSessionStore.completeThinkingReveal.bind(raysSessionStore),
  };
}