import { useState } from "react";
import { ChevronRight, ChevronDown, FileText, Folder, FolderOpen } from "lucide-react";
import type { FileNode } from "@/services/raysSession";

function TreeItem({ node, depth, path, onFileOpen }: { node: FileNode; depth: number; path: string; onFileOpen: (name: string) => void }) {
  const [open, setOpen] = useState(depth < 1);
  const fullPath = path ? `${path}/${node.name}` : node.name;

  if (node.type === "file") {
    return (
      <button
        className="flex items-center gap-1.5 w-full px-2 py-0.5 text-ui text-foreground/70 hover:text-foreground hover:bg-secondary/60 transition-colors"
        style={{ paddingLeft: `${depth * 14 + 8}px` }}
        onClick={() => onFileOpen(fullPath)}
      >
        <FileText size={13} className="text-rays-lilac shrink-0" />
        <span className="truncate">{node.name}</span>
      </button>
    );
  }

  return (
    <div>
      <button
        className="flex items-center gap-1 w-full px-2 py-0.5 text-ui font-medium text-foreground/80 hover:text-foreground hover:bg-secondary/60 transition-colors"
        style={{ paddingLeft: `${depth * 14 + 4}px` }}
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown size={12} className="text-rays-mid shrink-0" /> : <ChevronRight size={12} className="text-rays-mid shrink-0" />}
        {open ? <FolderOpen size={13} className="text-rays-lavender shrink-0" /> : <Folder size={13} className="text-rays-mid shrink-0" />}
        <span className="truncate">{node.name}</span>
      </button>
      {open && node.children?.map((child, index) => (
        <TreeItem key={`${fullPath}-${child.name}-${index}`} node={child} depth={depth + 1} path={fullPath} onFileOpen={onFileOpen} />
      ))}
    </div>
  );
}

export function FileExplorer({ onFileOpen, nodes }: { onFileOpen: (name: string) => void; nodes: FileNode[] }) {
  return (
    <div className="h-full bg-card overflow-y-auto">
      <div className="px-3 py-2 text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
        Explorer
      </div>
      <div className="pb-4">
        {nodes.length === 0 && <div className="px-3 py-1 text-xs text-muted-foreground">No workspace loaded</div>}
        {nodes.map((node, index) => (
          <TreeItem key={`${node.name}-${index}`} node={node} depth={0} path="" onFileOpen={onFileOpen} />
        ))}
      </div>
    </div>
  );
}
