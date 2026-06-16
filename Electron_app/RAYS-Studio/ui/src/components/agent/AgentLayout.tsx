import { useCallback, useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import { AppHeader } from "@/components/ide/AppHeader";
import { SettingsModal } from "@/components/ide/SettingsModal";
import { AgentSidebar } from "@/components/agent/AgentSidebar";
import { AgentChat } from "@/components/agent/AgentChat";
import { AgentExplorer } from "@/components/agent/AgentExplorer";
import { McpManagerPanel } from "@/components/agent/McpManagerPanel";
import { SkillsManagerPanel } from "@/components/agent/SkillsManagerPanel";
import { useRaysSession } from "@/hooks/useRaysSession";
import {
  AGENT_EXPLORER_WIDTH_KEY,
  AGENT_SIDEBAR_WIDTH_KEY,
  LAST_AGENT_SESSION_KEY,
} from "@/services/appStorage";
import { isElectronHost } from "@/services/platformHost";
import {
  bumpAgentSession,
  createAgentSession,
  listAgentSessions,
  type AgentSession,
} from "@/services/agentSessionStorage";
import { loadProviderSettings } from "@/services/workspaceStorage";

export default function AgentLayout() {
  const navigate = useNavigate();
  const [showSettings, setShowSettings] = useState(false);
  const [showMcp, setShowMcp] = useState(false);
  const [showSkills, setShowSkills] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(
    () => Number(localStorage.getItem(AGENT_SIDEBAR_WIDTH_KEY)) || 280
  );
  const [explorerWidth, setExplorerWidth] = useState(
    () => Number(localStorage.getItem(AGENT_EXPLORER_WIDTH_KEY)) || 300
  );
  const [activeSession, setActiveSession] = useState<AgentSession | null>(null);
  const [openingSessionId, setOpeningSessionId] = useState<string | null>(null);
  const [startingSession, setStartingSession] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const resumeAttempted = useRef(false);

  const {
    state,
    switchSession,
    stopSession,
    submitPrompt,
    respondApproval,
    setExecutionMode,
    refreshTree,
    selectFolder,
    reloadMcp,
  } = useRaysSession();

  const running = state.status === "running";
  const hasActiveChat = Boolean(
    state.sessionId || state.conversationId || state.turns.length > 0 || startingSession
  );

  const openSession = useCallback(
    async (session: AgentSession) => {
      if (
        state.conversationId === session.id &&
        state.sessionId &&
        state.connected &&
        !startingSession
      ) {
        setActiveSession(session);
        bumpAgentSession(session.id);
        return;
      }

      setOpeningSessionId(session.id);
      setStartingSession(true);
      setStartError(null);
      setActiveSession(session);

      try {
        await switchSession(session.workspacePath, session.id, loadProviderSettings());
        bumpAgentSession(session.id);
        localStorage.setItem(LAST_AGENT_SESSION_KEY, session.id);
      } catch (err) {
        setStartError(err instanceof Error ? err.message : "Failed to start session");
      } finally {
        setStartingSession(false);
        setOpeningSessionId(null);
      }
    },
    [
      startingSession,
      switchSession,
      state.connected,
      state.conversationId,
      state.sessionId,
    ]
  );

  const handleNewAgent = useCallback(async () => {
    const path = await selectFolder();
    if (!path) return;
    const session = createAgentSession(path);
    await openSession(session);
  }, [openSession, selectFolder]);

  const handleNewChat = useCallback(async () => {
    const workspacePath = state.workspaceRoot || activeSession?.workspacePath;
    if (!workspacePath) {
      await handleNewAgent();
      return;
    }
    const session = createAgentSession(workspacePath);
    await openSession(session);
  }, [activeSession?.workspacePath, handleNewAgent, openSession, state.workspaceRoot]);

  useEffect(() => {
    if (resumeAttempted.current || state.sessionId || state.conversationId || startingSession) return;
    const sessions = listAgentSessions();
    if (sessions.length === 0) return;
    resumeAttempted.current = true;
    const lastId = localStorage.getItem(LAST_AGENT_SESSION_KEY);
    const session = (lastId && sessions.find((s) => s.id === lastId)) || sessions[0];
    void openSession(session);
  }, [openSession, startingSession, state.sessionId]);

  useEffect(() => {
    if (!isElectronHost() || !window.raysDesktop?.onMenuAction) return;
    return window.raysDesktop.onMenuAction(async (action) => {
      if (action === "open-folder") {
        await handleNewAgent();
        return;
      }
      if (action === "close-workspace") {
        if (state.sessionId) await stopSession();
        setActiveSession(null);
        return;
      }
      if (action === "navigate-ide") {
        navigate("/ide");
      }
    });
  }, [handleNewAgent, navigate, state.sessionId, stopSession]);

  const beginHorizontalResize = useCallback(
    (event: ReactMouseEvent, side: "left" | "right") => {
      event.preventDefault();
      const startX = event.clientX;
      const startLeft = sidebarWidth;
      const startRight = explorerWidth;
      const onMouseMove = (moveEvent: MouseEvent) => {
        const delta = moveEvent.clientX - startX;
        if (side === "left") {
          const next = Math.max(200, Math.min(480, startLeft + delta));
          setSidebarWidth(next);
          localStorage.setItem(AGENT_SIDEBAR_WIDTH_KEY, String(next));
        } else {
          const next = Math.max(220, Math.min(560, startRight - delta));
          setExplorerWidth(next);
          localStorage.setItem(AGENT_EXPLORER_WIDTH_KEY, String(next));
        }
      };
      const onMouseUp = () => {
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };
      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [explorerWidth, sidebarWidth]
  );

  const openSkillsPanel = () => {
    setShowSkills(true);
    setShowMcp(false);
  };

  const openMcpPanel = () => {
    setShowMcp(true);
    setShowSkills(false);
  };

  const skillsWorkspace = state.workspaceRoot || activeSession?.workspacePath || null;

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-background">
      <AppHeader
        onOpenSettings={() => setShowSettings(true)}
        onOpenSkills={openSkillsPanel}
        onOpenMcp={openMcpPanel}
      />

      <div className="flex-1 flex min-h-0">
        <div style={{ width: leftCollapsed ? 40 : sidebarWidth }} className="shrink-0 h-full relative">
          <AgentSidebar
            collapsed={leftCollapsed}
            onToggleCollapse={() => setLeftCollapsed((v) => !v)}
            activeSessionId={activeSession?.id || state.conversationId}
            openingSessionId={openingSessionId}
            onNewAgent={() => void handleNewAgent()}
            onNewChat={() => void handleNewChat()}
            onSelectSession={(session) => void openSession(session)}
            onOpenSkills={openSkillsPanel}
            onOpenMcp={openMcpPanel}
          />
          {!leftCollapsed && (
            <div
              className="absolute top-0 right-0 w-1 h-full cursor-col-resize hover:bg-rays-lilac/40"
              onMouseDown={(e) => beginHorizontalResize(e, "left")}
            />
          )}
        </div>

        <div className="flex-1 min-w-0 flex flex-col">
          {!hasActiveChat ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 p-8">
              <h1 className="text-2xl font-semibold">RAYS Agent</h1>
              <p className="text-muted-foreground text-sm text-center max-w-md">
                {startingSession
                  ? "Loading chat…"
                  : "Pick a chat in the sidebar, or start a new agent in a folder. Skills and MCP are always available from the sidebar or top bar."}
              </p>
              {(startError || state.error) && (
                <div className="text-sm text-red-400 max-w-lg text-center">{startError || state.error}</div>
              )}
              <button
                type="button"
                disabled={startingSession}
                onClick={() => void handleNewAgent()}
                className="px-4 py-2 rounded-lg bg-rays-violet text-sm font-medium disabled:opacity-50"
              >
                {startingSession ? "Starting…" : "New Agent in Folder…"}
              </button>
            </div>
          ) : (
            <AgentChat
              turns={state.turns}
              connected={state.connected}
              running={running}
              loading={startingSession || state.status === "starting"}
              hudPhase={state.hudPhase}
              hudDetail={state.hudDetail}
              tokenCount={state.tokenCount}
              pendingApproval={state.pendingApproval}
              defaultMode="agent"
              onSend={(prompt, mode) => submitPrompt(prompt, mode || "agent")}
              onApprove={respondApproval}
            />
          )}
        </div>

        {hasActiveChat && (
          <div style={{ width: rightCollapsed ? 40 : explorerWidth }} className="shrink-0 h-full relative">
            {!rightCollapsed && (
              <div
                className="absolute top-0 left-0 w-1 h-full cursor-col-resize hover:bg-rays-lilac/40 z-10"
                onMouseDown={(e) => beginHorizontalResize(e, "right")}
              />
            )}
            <AgentExplorer
              collapsed={rightCollapsed}
              onToggleCollapse={() => setRightCollapsed((v) => !v)}
              nodes={state.fileTree}
              workspaceRoot={state.workspaceRoot}
              onRefresh={refreshTree}
            />
          </div>
        )}
      </div>

      <div className="h-7 border-t px-3 flex items-center justify-between text-[10px] text-muted-foreground bg-card/80" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
        <span>{state.workspaceRoot || activeSession?.workspacePath || "No workspace"}</span>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={state.executionMode === "autonomous"}
              onChange={(e) => setExecutionMode(e.target.checked ? "autonomous" : "ask")}
              disabled={!state.sessionId}
            />
            Autonomous mode
          </label>
          <span>{state.sessionId ? state.status : "no session"}</span>
        </div>
      </div>

      <SettingsModal open={showSettings} onClose={() => setShowSettings(false)} />
      <McpManagerPanel
        open={showMcp}
        onClose={() => setShowMcp(false)}
        workspaceRoot={skillsWorkspace}
        sessionActive={Boolean(state.sessionId && state.connected)}
        onReloadMcp={reloadMcp}
      />
      <SkillsManagerPanel open={showSkills} onClose={() => setShowSkills(false)} workspaceRoot={skillsWorkspace} />
    </div>
  );
}
