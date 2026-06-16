import { useState, useCallback, useEffect, type MouseEvent as ReactMouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import { AppHeader } from "@/components/ide/AppHeader";
import { FileExplorer } from "@/components/ide/FileExplorer";
import { DiffStream } from "@/components/ide/DiffStream";
import { AgentPanel } from "@/components/ide/AgentPanel";
import { TerminalPanel } from "@/components/ide/TerminalPanel";
import { SettingsModal } from "@/components/ide/SettingsModal";
import { McpManagerPanel } from "@/components/agent/McpManagerPanel";
import { SkillsManagerPanel } from "@/components/agent/SkillsManagerPanel";
import { StatusBar } from "@/components/ide/StatusBar";
import { CodeEditor } from "@/components/ide/CodeEditor";
import { PanelToggle } from "@/components/ide/PanelToggle";
import { WorkspaceLauncher } from "@/components/ide/WorkspaceLauncher";
import { useRaysSession } from "@/hooks/useRaysSession";
import { isElectronHost } from "@/services/platformHost";
import { X } from "lucide-react";

export default function IDELayout() {
  const navigate = useNavigate();
  const [startingSession, setStartingSession] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [showExplorer, setShowExplorer] = useState(true);
  const [showAgent, setShowAgent] = useState(true);
  const [showTerminal, setShowTerminal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showMcp, setShowMcp] = useState(false);
  const [showSkills, setShowSkills] = useState(false);
  const [openTabs, setOpenTabs] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [explorerWidth, setExplorerWidth] = useState(260);
  const [agentWidth, setAgentWidth] = useState(340);
  const [terminalHeight, setTerminalHeight] = useState(200);
  const { state, startSession, stopSession, submitPrompt, sendTerminalInput, selectFolder, readFile, completeThinkingReveal, reloadMcp } =
    useRaysSession();

  const showLauncher = !state.sessionId;

  const openWorkspace = useCallback(
    async (workspacePath: string) => {
      setStartingSession(true);
      setStartError(null);
      try {
        await startSession(workspacePath);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to start session";
        setStartError(message);
      } finally {
        setStartingSession(false);
      }
    },
    [startSession]
  );

  useEffect(() => {
    if (!isElectronHost() || !window.raysDesktop?.onMenuAction) return;
    return window.raysDesktop.onMenuAction(async (action) => {
      if (action === "open-folder") {
        const path = await selectFolder();
        if (path) await openWorkspace(path);
        return;
      }
      if (action === "show-launcher") {
        if (state.sessionId) await stopSession();
        return;
      }
      if (action === "close-workspace") {
        if (state.sessionId) await stopSession();
        return;
      }
      if (action === "navigate-agent") {
        navigate("/agent");
      }
    });
  }, [navigate, openWorkspace, selectFolder, state.sessionId, stopSession]);

  const handleFileOpen = (fileName: string) => {
    if (!openTabs.includes(fileName)) {
      setOpenTabs((prev) => [...prev, fileName]);
    }
    setActiveTab(fileName);
  };

  const handleCloseTab = (fileName: string) => {
    setOpenTabs((prev) => prev.filter((t) => t !== fileName));
    if (activeTab === fileName) {
      setActiveTab(null);
    }
  };

  const beginHorizontalResize = useCallback(
    (event: ReactMouseEvent, side: "left" | "right") => {
      event.preventDefault();
      const startX = event.clientX;
      const startLeft = explorerWidth;
      const startRight = agentWidth;
      const onMouseMove = (moveEvent: MouseEvent) => {
        const delta = moveEvent.clientX - startX;
        if (side === "left") {
          const next = Math.max(180, Math.min(560, startLeft + delta));
          setExplorerWidth(next);
        } else {
          const next = Math.max(260, Math.min(620, startRight - delta));
          setAgentWidth(next);
        }
      };
      const onMouseUp = () => {
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };
      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [agentWidth, explorerWidth]
  );

  const beginVerticalResize = useCallback(
    (event: ReactMouseEvent) => {
      event.preventDefault();
      const startY = event.clientY;
      const startHeight = terminalHeight;
      const onMouseMove = (moveEvent: MouseEvent) => {
        const delta = startY - moveEvent.clientY;
        const next = Math.max(140, Math.min(420, startHeight + delta));
        setTerminalHeight(next);
      };
      const onMouseUp = () => {
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };
      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [terminalHeight]
  );

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-background">
      <WorkspaceLauncher
        open={showLauncher}
        busy={startingSession}
        error={startError || state.error}
        onOpenFolder={selectFolder}
        onOpenWorkspace={openWorkspace}
      />

      <AppHeader
        onOpenSettings={() => setShowSettings(true)}
        onOpenSkills={() => {
          setShowSkills(true);
          setShowMcp(false);
        }}
        onOpenMcp={() => {
          setShowMcp(true);
          setShowSkills(false);
        }}
      />

      <div
        className="h-[30px] bg-card/50 flex items-center justify-between px-3 border-b"
        style={{ borderColor: "rgba(255,255,255,0.05)" }}
      >
        <div className="flex items-center gap-2 min-w-0">
          {state.workspaceRoot && (
            <span className="text-[10px] text-muted-foreground truncate max-w-md" title={state.workspaceRoot}>
              {state.workspaceRoot}
            </span>
          )}
          {openTabs.length === 0 && !state.workspaceRoot && (
            <span className="text-[10px] text-muted-foreground">Diff Stream</span>
          )}
          {openTabs.map((tab) => (
            <div
              key={tab}
              className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-sm text-[11px] cursor-pointer transition-colors ${activeTab === tab ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"}`}
              onClick={() => setActiveTab(tab)}
            >
              <span>{tab}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleCloseTab(tab);
                }}
                className="hover:text-rays-pink transition-colors"
              >
                <X size={10} />
              </button>
            </div>
          ))}
        </div>
        <PanelToggle
          showExplorer={showExplorer}
          showAgent={showAgent}
          showTerminal={showTerminal}
          onToggleExplorer={() => setShowExplorer(!showExplorer)}
          onToggleAgent={() => setShowAgent(!showAgent)}
          onToggleTerminal={() => setShowTerminal(!showTerminal)}
        />
      </div>

      <div className="flex-1 flex overflow-hidden">
        {showExplorer && (
          <div
            className="shrink-0 border-r overflow-hidden"
            style={{ width: `${explorerWidth}px`, borderColor: "rgba(255,255,255,0.05)" }}
          >
            <FileExplorer onFileOpen={handleFileOpen} nodes={state.fileTree} />
          </div>
        )}
        {showExplorer && (
          <div
            className="w-1 shrink-0 cursor-col-resize hover:bg-rays-pink/30"
            onMouseDown={(event) => beginHorizontalResize(event, "left")}
          />
        )}

        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-hidden">
            {activeTab ? (
              <CodeEditor
                fileName={activeTab}
                fileContent={state.fileContents[activeTab]}
                onLoadFile={readFile}
              />
            ) : (
              <DiffStream connected={state.connected} chunks={state.diffChunks} />
            )}
          </div>
          {showTerminal && (
            <>
              <div
                className="h-1 shrink-0 cursor-row-resize hover:bg-rays-pink/30"
                onMouseDown={beginVerticalResize}
              />
              <div
                className="shrink-0 border-t overflow-hidden"
                style={{ height: `${terminalHeight}px`, borderColor: "rgba(255,255,255,0.05)" }}
              >
                <TerminalPanel
                  lines={state.terminalLines}
                  connected={state.connected}
                  onSubmitInput={sendTerminalInput}
                />
              </div>
            </>
          )}
        </div>

        {showAgent && (
          <>
            <div
              className="w-1 shrink-0 cursor-col-resize hover:bg-rays-pink/30"
              onMouseDown={(event) => beginHorizontalResize(event, "right")}
            />
            <div
              className="shrink-0 border-l overflow-hidden"
              style={{ width: `${agentWidth}px`, borderColor: "rgba(255,255,255,0.05)" }}
            >
              <AgentPanel
                messages={state.chatMessages}
                connected={state.connected}
                running={state.status === "running"}
                thinkingPhase={state.thinkingPhase}
                thinkingText={state.thinkingText}
                onSend={(prompt) => submitPrompt(prompt, "code")}
                onThinkingRevealComplete={completeThinkingReveal}
              />
            </div>
          </>
        )}
      </div>

      <StatusBar />

      <SettingsModal open={showSettings} onClose={() => setShowSettings(false)} />
      <McpManagerPanel
        open={showMcp}
        onClose={() => setShowMcp(false)}
        workspaceRoot={state.workspaceRoot}
        sessionActive={Boolean(state.sessionId && state.connected)}
        onReloadMcp={reloadMcp}
      />
      <SkillsManagerPanel
        open={showSkills}
        onClose={() => setShowSkills(false)}
        workspaceRoot={state.workspaceRoot}
      />
    </div>
  );
}
