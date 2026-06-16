import { FileExplorer } from "@/components/ide/FileExplorer";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { FileNode } from "@/services/raysSession";

type AgentExplorerProps = {
  collapsed: boolean;
  onToggleCollapse: () => void;
  nodes: FileNode[];
  workspaceRoot: string | null;
  onRefresh?: () => void;
};

export function AgentExplorer({ collapsed, onToggleCollapse, nodes, workspaceRoot, onRefresh }: AgentExplorerProps) {
  if (collapsed) {
    return (
      <div className="h-full w-10 bg-card border-l flex flex-col items-center py-2" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
        <button type="button" onClick={onToggleCollapse} className="p-1.5 rounded hover:bg-secondary" title="Expand explorer">
          <ChevronLeft size={16} />
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-card border-l" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
      <div className="px-3 py-2 border-b flex items-center justify-between gap-2" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
        <div className="min-w-0">
          <div className="text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">Explorer</div>
          {workspaceRoot && (
            <div className="text-[10px] text-muted-foreground truncate" title={workspaceRoot}>
              {workspaceRoot.split(/[/\\]/).pop()}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {onRefresh && (
            <button type="button" onClick={onRefresh} className="text-[10px] px-1.5 py-0.5 rounded hover:bg-secondary">
              Refresh
            </button>
          )}
          <button type="button" onClick={onToggleCollapse} className="p-1 rounded hover:bg-secondary" title="Collapse explorer">
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <FileExplorer nodes={nodes} onFileOpen={() => {}} />
      </div>
    </div>
  );
}
