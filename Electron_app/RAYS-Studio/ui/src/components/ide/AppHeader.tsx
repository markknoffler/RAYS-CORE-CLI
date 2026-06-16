import { NavLink } from "react-router-dom";
import { BookOpen, Plug } from "lucide-react";

type AppHeaderProps = {
  onOpenSettings: () => void;
  onOpenSkills?: () => void;
  onOpenMcp?: () => void;
};

export function AppHeader({ onOpenSettings, onOpenSkills, onOpenMcp }: AppHeaderProps) {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
      isActive ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
    }`;

  const toolBtn =
    "px-2 py-1 rounded text-[11px] font-medium inline-flex items-center gap-1 text-muted-foreground hover:text-foreground hover:bg-secondary/60 transition-colors";

  return (
    <div
      className="h-9 bg-card flex items-center justify-between px-3 select-none border-b"
      style={{ borderColor: "rgba(255,255,255,0.05)" }}
    >
      <div className="flex items-center gap-3">
        <span className="font-extrabold tracking-wider text-sm text-rays-pink">RAYS</span>
        <nav className="flex items-center gap-1">
          <NavLink to="/agent" className={linkClass}>
            Agent
          </NavLink>
          <NavLink to="/ide" className={linkClass}>
            IDE
          </NavLink>
        </nav>
      </div>
      <div className="flex items-center gap-1">
        {onOpenSkills && (
          <button type="button" className={toolBtn} onClick={onOpenSkills} title="Add and manage skills">
            <BookOpen size={13} />
            Skills
          </button>
        )}
        {onOpenMcp && (
          <button type="button" className={toolBtn} onClick={onOpenMcp} title="Add and manage MCP servers">
            <Plug size={13} />
            MCP
          </button>
        )}
        <button
          onClick={onOpenSettings}
          className="p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
          title="Settings"
          type="button"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l-.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </button>
      </div>
    </div>
  );
}
