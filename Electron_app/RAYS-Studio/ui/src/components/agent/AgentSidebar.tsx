import { BookOpen, ChevronLeft, ChevronRight, FolderOpen, Loader2, MessageSquarePlus, Plug, Plus } from "lucide-react";
import { useAgentSessions } from "@/hooks/useAgentSessions";
import { workspaceLabel, type AgentSession } from "@/services/agentSessionStorage";

type AgentSidebarProps = {
  collapsed: boolean;
  onToggleCollapse: () => void;
  activeSessionId: string | null;
  openingSessionId: string | null;
  onNewAgent: () => void;
  onNewChat: () => void;
  onSelectSession: (session: AgentSession) => void;
  onOpenSkills: () => void;
  onOpenMcp: () => void;
};

export function AgentSidebar({
  collapsed,
  onToggleCollapse,
  activeSessionId,
  openingSessionId,
  onNewAgent,
  onNewChat,
  onSelectSession,
  onOpenSkills,
  onOpenMcp,
}: AgentSidebarProps) {
  const { sessions, grouped } = useAgentSessions();
  const workspacePaths = Object.keys(grouped).sort((a, b) => {
    const aMax = Math.max(...grouped[a].map((s) => s.updatedAt));
    const bMax = Math.max(...grouped[b].map((s) => s.updatedAt));
    return bMax - aMax;
  });

  if (collapsed) {
    return (
      <div className="h-full w-10 bg-card border-r flex flex-col items-center py-2 gap-2" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
        <button type="button" onClick={onToggleCollapse} className="p-1.5 rounded hover:bg-secondary" title="Expand sidebar">
          <ChevronRight size={16} />
        </button>
        <button type="button" onClick={onNewAgent} className="p-1.5 rounded hover:bg-secondary" title="New agent">
          <Plus size={16} />
        </button>
        <button type="button" onClick={onNewChat} className="p-1.5 rounded hover:bg-secondary" title="New chat">
          <MessageSquarePlus size={16} />
        </button>
        <button type="button" onClick={onOpenSkills} className="p-1.5 rounded hover:bg-secondary" title="Skills — add skill folder">
          <BookOpen size={16} />
        </button>
        <button type="button" onClick={onOpenMcp} className="p-1.5 rounded hover:bg-secondary" title="MCP Servers">
          <Plug size={16} />
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-card border-r" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
      <div className="p-3 border-b flex items-center justify-between" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
        <span className="text-xs font-semibold tracking-widest uppercase text-muted-foreground">Sessions</span>
        <button type="button" onClick={onToggleCollapse} className="p-1 rounded hover:bg-secondary" title="Collapse sidebar">
          <ChevronLeft size={14} />
        </button>
      </div>

      <div className="p-2 space-y-1 border-b" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
        <button
          type="button"
          onClick={onNewAgent}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm hover:bg-secondary transition-colors text-left"
        >
          <Plus size={14} />
          New Agent
        </button>
        <button
          type="button"
          onClick={onNewChat}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm hover:bg-secondary transition-colors text-left"
        >
          <MessageSquarePlus size={14} />
          New Chat
        </button>
        <button
          type="button"
          onClick={onOpenSkills}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm hover:bg-secondary transition-colors text-left"
        >
          <BookOpen size={14} />
          Add Skill…
        </button>
        <button
          type="button"
          onClick={onOpenMcp}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm hover:bg-secondary transition-colors text-left"
        >
          <Plug size={14} />
          MCP Servers
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-3 min-h-0">
        {workspacePaths.length === 0 && (
          <div className="px-2 py-4 text-xs text-muted-foreground">
            No chats yet. Use New Agent to open a folder, or pick Skills / MCP above anytime.
          </div>
        )}
        {workspacePaths.map((workspacePath) => (
          <div key={workspacePath}>
            <div className="flex items-center gap-1.5 px-2 py-1 text-[11px] font-semibold text-foreground/80">
              <FolderOpen size={12} className="text-rays-lavender shrink-0" />
              <span className="truncate" title={workspacePath}>
                {workspaceLabel(workspacePath)}
              </span>
            </div>
            <div className="space-y-0.5 mt-0.5">
              {grouped[workspacePath].map((session) => {
                const isActive = activeSessionId === session.id;
                const isOpening = openingSessionId === session.id;
                return (
                  <button
                    key={session.id}
                    type="button"
                    disabled={false}
                    onClick={() => onSelectSession(session)}
                    className={`w-full text-left px-2 py-1.5 rounded text-xs truncate transition-colors flex items-center gap-1.5 ${
                      isActive
                        ? "bg-secondary text-foreground"
                        : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
                    } disabled:opacity-40`}
                    title={session.title}
                  >
                    {isOpening && <Loader2 size={12} className="shrink-0 animate-spin" />}
                    <span className="truncate">{session.title}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="p-2 border-t text-[10px] text-muted-foreground" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
        {sessions.length} chat{sessions.length === 1 ? "" : "s"} — click to reopen
      </div>
    </div>
  );
}
