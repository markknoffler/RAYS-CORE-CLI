import { useCallback, useEffect, useState } from "react";
import {
  hostInstallSkill,
  hostListSkills,
  hostOpenSkillsDirectory,
  hostSelectSkillFolder,
  isElectronHost,
} from "@/services/platformHost";

type SkillEntry = {
  name: string;
  scope: "global" | "project";
  path: string;
  description?: string;
};

type SkillsManagerPanelProps = {
  open: boolean;
  onClose: () => void;
  workspaceRoot: string | null;
};

function installTargetLabel(scope: "global" | "project", workspaceRoot: string | null): string {
  if (scope === "global") return "~/.rays/skills/";
  if (!workspaceRoot) return "./skills/ (open a workspace first)";
  return `${workspaceRoot}/skills/`;
}

export function SkillsManagerPanel({ open, onClose, workspaceRoot }: SkillsManagerPanelProps) {
  const [skills, setSkills] = useState<SkillEntry[]>([]);
  const [scope, setScope] = useState<"global" | "project">("project");
  const [selectedFolder, setSelectedFolder] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const desktop = isElectronHost();

  const reload = useCallback(async () => {
    if (!open) return;
    setError(null);
    try {
      const items = await hostListSkills(workspaceRoot || undefined);
      setSkills(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to list skills");
    }
  }, [open, workspaceRoot]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!open) {
      setSelectedFolder("");
      setError(null);
    }
  }, [open]);

  const handleBrowse = async () => {
    if (!desktop) {
      setError("Adding skills requires the RAYS Studio desktop app");
      return;
    }
    setError(null);
    try {
      const folder = await hostSelectSkillFolder();
      if (folder) setSelectedFolder(folder);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to choose folder");
    }
  };

  const handleAdd = async () => {
    if (!desktop) {
      setError("Adding skills requires the RAYS Studio desktop app");
      return;
    }
    if (scope === "project" && !workspaceRoot) {
      setError("Open a workspace to install project skills");
      return;
    }
    if (!selectedFolder) {
      setError("Choose a skill folder first");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await hostInstallSkill(scope, workspaceRoot || undefined, selectedFolder);
      setSelectedFolder("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to install skill");
    } finally {
      setBusy(false);
    }
  };

  const handleOpenTargetFolder = async () => {
    if (!desktop) {
      setError("Opening skill folders requires the RAYS Studio desktop app");
      return;
    }
    if (scope === "project" && !workspaceRoot) {
      setError("Open a workspace to view project skills folder");
      return;
    }
    setError(null);
    try {
      await hostOpenSkillsDirectory(scope, workspaceRoot || undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open folder");
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-xl border bg-card shadow-xl">
        <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
          <div>
            <h2 className="text-lg font-semibold">Skills</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Browse a skill folder, pick global or project scope, then Add to install.
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-sm px-2 py-1 rounded hover:bg-secondary">
            Close
          </button>
        </div>

        <div className="p-4 space-y-4">
          {!desktop && (
            <div className="text-sm text-amber-300 bg-amber-950/30 border border-amber-900/40 rounded p-2">
              Skill install is available in the packaged desktop app.
            </div>
          )}

          {error && (
            <div className="text-sm text-red-400 bg-red-950/30 border border-red-900/40 rounded p-2">{error}</div>
          )}

          <div>
            <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">Installed</div>
            {skills.length === 0 ? (
              <div className="text-sm text-muted-foreground">No skills found. Add a folder containing SKILL.md.</div>
            ) : (
              <div className="space-y-2">
                {skills.map((skill) => (
                  <div key={`${skill.scope}-${skill.name}`} className="p-2 rounded border bg-secondary/30">
                    <div className="text-sm font-medium">{skill.name}</div>
                    <div className="text-[10px] uppercase tracking-wider text-rays-lilac">{skill.scope}</div>
                    <div className="text-[10px] text-muted-foreground truncate" title={skill.path}>
                      {skill.path}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="border-t pt-4 space-y-3" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
            <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Add skill</div>

            <div className="flex gap-2">
              <button
                type="button"
                className={`text-xs px-2 py-1 rounded ${scope === "global" ? "bg-rays-violet" : "bg-secondary"}`}
                onClick={() => setScope("global")}
              >
                Global (~/.rays/skills)
              </button>
              <button
                type="button"
                className={`text-xs px-2 py-1 rounded ${scope === "project" ? "bg-rays-violet" : "bg-secondary"}`}
                onClick={() => setScope("project")}
                disabled={!workspaceRoot}
              >
                Project (./skills)
              </button>
            </div>

            <div className="text-[11px] text-muted-foreground">
              Install to: <span className="text-foreground/90">{installTargetLabel(scope, workspaceRoot)}</span>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void handleBrowse()}
                disabled={busy || !desktop}
                className="px-3 py-1.5 rounded bg-secondary text-sm font-medium disabled:opacity-50"
              >
                Browse skill folder…
              </button>
              <button
                type="button"
                onClick={() => void handleAdd()}
                disabled={busy || !desktop || !selectedFolder}
                className="px-3 py-1.5 rounded bg-rays-violet text-sm font-medium disabled:opacity-50"
              >
                {busy ? "Adding…" : "Add skill"}
              </button>
              <button
                type="button"
                onClick={() => void handleOpenTargetFolder()}
                disabled={busy || !desktop || (scope === "project" && !workspaceRoot)}
                className="px-3 py-1.5 rounded border text-sm disabled:opacity-50"
                style={{ borderColor: "rgba(255,255,255,0.12)" }}
              >
                Open skills folder
              </button>
            </div>

            {selectedFolder ? (
              <div className="text-xs rounded border bg-secondary/20 p-2" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
                <div className="text-muted-foreground mb-0.5">Selected folder</div>
                <div className="truncate font-mono text-[11px]" title={selectedFolder}>
                  {selectedFolder}
                </div>
                <div className="text-[10px] text-muted-foreground mt-1">Must contain SKILL.md — validated when you click Add.</div>
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">
                Pick any folder that contains a SKILL.md file, then click Add skill to copy it into the scope above.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
