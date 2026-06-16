import { useState } from "react";
import type { ProviderConfig } from "@/services/raysSession";

type WorkspacePickerProps = {
  open: boolean;
  busy?: boolean;
  error?: string | null;
  onBrowse: () => Promise<string>;
  onStart: (workspacePath: string, providerConfig: ProviderConfig) => Promise<void> | void;
};

export function WorkspacePicker({ open, busy = false, error, onBrowse, onStart }: WorkspacePickerProps) {
  const [workspacePath, setWorkspacePath] = useState("");
  const [provider, setProvider] = useState<ProviderConfig["provider"]>("ollama");
  const [model, setModel] = useState("qwen2.5-coder:latest");
  const [apiKey, setApiKey] = useState("");
  const [browseError, setBrowseError] = useState<string | null>(null);

  if (!open) return null;

  const handleStart = async () => {
    if (!workspacePath.trim()) return;
    await onStart(workspacePath.trim(), { provider, model: model.trim(), apiKey: apiKey.trim() });
  };

  const handleBrowse = async () => {
    setBrowseError(null);
    try {
      const folderPath = await onBrowse();
      if (folderPath) {
        setWorkspacePath(folderPath);
      }
    } catch (browseErr) {
      setBrowseError(browseErr instanceof Error ? browseErr.message : "Failed to open folder picker");
    }
  };

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/50">
      <div className="w-full max-w-xl rounded-xl border bg-card p-5 shadow-2xl" style={{ borderColor: "hsl(255 50% 60% / 0.2)" }}>
        <div className="text-lg font-semibold text-foreground">Open Workspace</div>
        <p className="mt-1 text-sm text-muted-foreground">
          Select the absolute folder path to anchor this RAYS session.
        </p>
        <div className="mt-4 space-y-2">
          <label htmlFor="workspace-path" className="text-xs tracking-widest uppercase text-muted-foreground">
            Workspace Path
          </label>
          <div className="flex gap-2">
            <input
              id="workspace-path"
              value={workspacePath}
              onChange={(e) => setWorkspacePath(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleStart()}
              placeholder="/Users/you/project"
              className="flex-1 rounded-md border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-rays-pink"
              style={{ borderColor: "hsl(255 50% 60% / 0.2)" }}
            />
            <button
              onClick={handleBrowse}
              disabled={busy}
              className="rounded-md border px-3 py-2 text-sm text-foreground hover:bg-secondary disabled:opacity-50"
              style={{ borderColor: "hsl(255 50% 60% / 0.2)" }}
            >
              Browse
            </button>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="space-y-2">
            <label htmlFor="provider" className="text-xs tracking-widest uppercase text-muted-foreground">
              Provider
            </label>
            <select
              id="provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value as ProviderConfig["provider"])}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-rays-pink"
              style={{ borderColor: "hsl(255 50% 60% / 0.2)" }}
            >
              <option value="ollama">Ollama</option>
              <option value="gemini">Gemini API</option>
              <option value="openai">OpenAI API</option>
            </select>
          </div>
          <div className="space-y-2">
            <label htmlFor="model" className="text-xs tracking-widest uppercase text-muted-foreground">
              Model
            </label>
            <input
              id="model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={provider === "ollama" ? "qwen2.5-coder:latest" : provider === "gemini" ? "gemini-1.5-flash" : "gpt-4o"}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-rays-pink"
              style={{ borderColor: "hsl(255 50% 60% / 0.2)" }}
            />
          </div>
        </div>
        {provider !== "ollama" && (
          <div className="mt-3 space-y-2">
            <label htmlFor="api-key" className="text-xs tracking-widest uppercase text-muted-foreground">
              API Key (session only)
            </label>
            <input
              id="api-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-rays-pink"
              style={{ borderColor: "hsl(255 50% 60% / 0.2)" }}
            />
          </div>
        )}
        {(error || browseError) && <div className="mt-3 text-xs text-diff-remove">{error || browseError}</div>}
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={handleStart}
            disabled={busy || !workspacePath.trim() || !model.trim()}
            className="rounded-md bg-rays-pink/20 px-4 py-2 text-sm text-rays-pink transition-colors hover:bg-rays-pink/30 disabled:opacity-50"
          >
            {busy ? "Starting..." : "Start Session"}
          </button>
        </div>
      </div>
    </div>
  );
}
