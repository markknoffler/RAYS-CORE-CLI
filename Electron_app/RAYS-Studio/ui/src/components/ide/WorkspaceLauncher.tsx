import { useEffect, useState } from "react";
import { FolderOpen, Clock, Trash2 } from "lucide-react";
import {
  loadRecentWorkspaces,
  removeRecentWorkspace,
  type RecentWorkspace,
} from "@/services/workspaceStorage";

type WorkspaceLauncherProps = {
  open: boolean;
  busy?: boolean;
  error?: string | null;
  onOpenFolder: () => Promise<string>;
  onOpenWorkspace: (workspacePath: string) => Promise<void> | void;
};

export function WorkspaceLauncher({
  open,
  busy = false,
  error,
  onOpenFolder,
  onOpenWorkspace,
}: WorkspaceLauncherProps) {
  const [recent, setRecent] = useState<RecentWorkspace[]>([]);
  const [browseError, setBrowseError] = useState<string | null>(null);

  useEffect(() => {
    if (open) setRecent(loadRecentWorkspaces());
  }, [open]);

  if (!open) return null;

  const handleBrowse = async () => {
    setBrowseError(null);
    try {
      const folderPath = await onOpenFolder();
      if (folderPath) await onOpenWorkspace(folderPath);
    } catch (browseErr) {
      setBrowseError(
        browseErr instanceof Error ? browseErr.message : "Failed to open folder picker"
      );
    }
  };

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/50">
      <div
        className="w-full max-w-lg rounded-xl border bg-card p-6 shadow-2xl"
        style={{ borderColor: "hsl(255 50% 60% / 0.2)" }}
      >
        <div className="text-lg font-semibold text-foreground">RAYS Studio</div>
        <p className="mt-1 text-sm text-muted-foreground">
          Open a project folder. Provider and model use your last settings (change in Settings).
        </p>

        <button
          onClick={handleBrowse}
          disabled={busy}
          className="mt-5 flex w-full items-center justify-center gap-2 rounded-md bg-rays-pink/20 px-4 py-2.5 text-sm text-rays-pink transition-colors hover:bg-rays-pink/30 disabled:opacity-50"
        >
          <FolderOpen size={16} />
          {busy ? "Starting…" : "Open Folder…"}
        </button>

        {recent.length > 0 && (
          <div className="mt-6">
            <div className="mb-2 flex items-center gap-1.5 text-xs uppercase tracking-widest text-muted-foreground">
              <Clock size={12} />
              Recent
            </div>
            <ul className="max-h-48 space-y-1 overflow-y-auto">
              {recent.map((item) => (
                <li key={item.path} className="group flex items-center gap-1">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onOpenWorkspace(item.path)}
                    className="min-w-0 flex-1 rounded-md px-3 py-2 text-left text-sm text-foreground hover:bg-secondary disabled:opacity-50"
                    title={item.path}
                  >
                    <span className="block truncate font-medium">
                      {item.path.split("/").filter(Boolean).pop() || item.path}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {item.path}
                    </span>
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      removeRecentWorkspace(item.path);
                      setRecent(loadRecentWorkspaces());
                    }}
                    className="rounded p-1.5 text-muted-foreground opacity-0 transition-opacity hover:bg-secondary hover:text-foreground group-hover:opacity-100"
                    title="Remove from recent"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {(error || browseError) && (
          <div className="mt-3 text-xs text-diff-remove">{error || browseError}</div>
        )}
      </div>
    </div>
  );
}
