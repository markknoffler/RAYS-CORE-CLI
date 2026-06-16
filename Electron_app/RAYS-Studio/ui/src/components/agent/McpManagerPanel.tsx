import { useCallback, useEffect, useState } from "react";
import { Copy, RefreshCw } from "lucide-react";
import { MCP_EXAMPLE_JSON } from "@/data/mcpExample";
import { hostReadMcpConfig, hostRemoveMcpServer, hostWriteMcpConfig } from "@/services/platformHost";

export type McpServerEntry = {
  name: string;
  command: string;
  args?: string[];
  env?: Record<string, string>;
  description?: string;
  enabled?: boolean;
  quiet?: boolean;
  scope?: "global" | "project";
};

type McpManagerPanelProps = {
  open: boolean;
  onClose: () => void;
  workspaceRoot: string | null;
  sessionActive?: boolean;
  onReloadMcp?: () => void;
};

function parseServerJson(raw: string): McpServerEntry {
  const parsed = JSON.parse(raw) as Record<string, unknown>;
  const entry =
    Array.isArray(parsed.mcp_servers) && parsed.mcp_servers.length > 0
      ? (parsed.mcp_servers[0] as McpServerEntry)
      : (parsed as McpServerEntry);

  if (!entry.name || !entry.command) {
    throw new Error("JSON must include name and command (or mcp_servers[0])");
  }

  return entry;
}

export function McpManagerPanel({
  open,
  onClose,
  workspaceRoot,
  sessionActive = false,
  onReloadMcp,
}: McpManagerPanelProps) {
  const [servers, setServers] = useState<McpServerEntry[]>([]);
  const [scope, setScope] = useState<"global" | "project">("global");
  const [jsonDraft, setJsonDraft] = useState("");
  const [jsonFocused, setJsonFocused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    if (!open) return;
    setError(null);
    try {
      const global = await hostReadMcpConfig("global", workspaceRoot || undefined);
      const project =
        workspaceRoot != null ? await hostReadMcpConfig("project", workspaceRoot) : { mcp_servers: [] };
      const merged = [
        ...(global.mcp_servers || []).map((s) => ({ ...s, scope: "global" as const })),
        ...(project.mcp_servers || []).map((s) => ({ ...s, scope: "project" as const })),
      ];
      setServers(merged);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load MCP config");
    }
  }, [open, workspaceRoot]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!open) {
      setJsonDraft("");
      setJsonFocused(false);
      setInfo(null);
    }
  }, [open]);

  const handleSave = async () => {
    if (!jsonDraft.trim()) {
      setError("Paste or write MCP server JSON before saving");
      return;
    }
    if (scope === "project" && !workspaceRoot) {
      setError("Open a workspace to save project-scoped MCP servers");
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const entry = parseServerJson(jsonDraft);
      await hostWriteMcpConfig(scope, workspaceRoot || undefined, entry);
      setJsonDraft("");
      setJsonFocused(false);
      await reload();
      setInfo(
        sessionActive
          ? "Saved. Click Reload MCP below so this session picks up the change."
          : "Saved. Start or reload your agent session to connect."
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save MCP server");
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async (server: McpServerEntry) => {
    const serverScope = server.scope || "global";
    if (serverScope === "project" && !workspaceRoot) return;
    setBusy(true);
    setError(null);
    try {
      await hostRemoveMcpServer(serverScope, workspaceRoot || undefined, server.name);
      await reload();
      setInfo("Removed. Reload MCP if a session is already running.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove server");
    } finally {
      setBusy(false);
    }
  };

  const copyExample = async () => {
    try {
      await navigator.clipboard.writeText(MCP_EXAMPLE_JSON);
      setInfo("Example copied to clipboard.");
    } catch {
      setError("Could not copy example to clipboard");
    }
  };

  const useExample = () => {
    setJsonDraft(MCP_EXAMPLE_JSON);
    setJsonFocused(true);
    setError(null);
    setInfo("Example loaded — edit command/env if needed, then Save.");
  };

  const handleReloadMcp = () => {
    if (!onReloadMcp) {
      setError("Start an agent session first, then reload MCP.");
      return;
    }
    setInfo("Reloading MCP servers in this session…");
    onReloadMcp();
  };

  if (!open) return null;

  const showExampleShadow = !jsonDraft && !jsonFocused;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border bg-card shadow-xl">
        <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
          <div>
            <h2 className="text-lg font-semibold">MCP Servers</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Paste the same JSON as Cursor/Hermes · saved to ~/.rays/mcp.json or &lt;project&gt;/.rays/mcp.json
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-sm px-2 py-1 rounded hover:bg-secondary">
            Close
          </button>
        </div>

        <div className="p-4 space-y-4">
          {error && (
            <div className="text-sm text-red-400 bg-red-950/30 border border-red-900/40 rounded p-2">{error}</div>
          )}
          {info && (
            <div className="text-sm text-emerald-300/90 bg-emerald-950/20 border border-emerald-900/30 rounded p-2">
              {info}
            </div>
          )}

          <div className="text-xs text-muted-foreground rounded border p-2 bg-secondary/20" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
            Blender: keep Blender open with the MCP addon connected (N panel → BlenderMCP → Connect, port 9876).
            Optional tools (Hyper3D, Hunyuan) may fail without killing the connection — use execute_blender_code to build
            geometry when those services are offline.
          </div>

          <div>
            <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">Configured</div>
            {servers.length === 0 ? (
              <div className="text-sm text-muted-foreground">No MCP servers configured yet.</div>
            ) : (
              <div className="space-y-2">
                {servers.map((server) => (
                  <div
                    key={`${server.scope}-${server.name}`}
                    className="flex items-start justify-between gap-2 p-2 rounded border bg-secondary/30"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium">{server.name}</div>
                      <div className="text-xs text-muted-foreground truncate">{server.command}</div>
                      <div className="text-[10px] uppercase tracking-wider text-rays-lilac mt-1">{server.scope}</div>
                    </div>
                    <button
                      type="button"
                      className="text-xs px-2 py-1 rounded hover:bg-secondary shrink-0"
                      onClick={() => void handleRemove(server)}
                      disabled={busy}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="border-t pt-4" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
            <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
              <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Add server</div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={useExample}
                  className="text-xs px-2 py-1 rounded bg-secondary hover:bg-secondary/80"
                >
                  Use example
                </button>
                <button
                  type="button"
                  onClick={() => void copyExample()}
                  className="text-xs px-2 py-1 rounded bg-secondary hover:bg-secondary/80 inline-flex items-center gap-1"
                >
                  <Copy size={12} />
                  Copy example
                </button>
              </div>
            </div>

            <div className="flex gap-2 mb-3">
              <button
                type="button"
                className={`text-xs px-2 py-1 rounded ${scope === "global" ? "bg-rays-violet" : "bg-secondary"}`}
                onClick={() => setScope("global")}
              >
                Global
              </button>
              <button
                type="button"
                className={`text-xs px-2 py-1 rounded ${scope === "project" ? "bg-rays-violet" : "bg-secondary"}`}
                onClick={() => setScope("project")}
                disabled={!workspaceRoot}
              >
                Project
              </button>
            </div>

            <div className="relative rounded-lg border bg-background min-h-[220px]" style={{ borderColor: "rgba(255,255,255,0.1)" }}>
              {showExampleShadow && (
                <pre
                  className="absolute inset-0 p-3 text-[11px] font-mono leading-relaxed text-muted-foreground/35 pointer-events-none whitespace-pre-wrap break-words overflow-hidden select-none"
                  aria-hidden
                >
                  {MCP_EXAMPLE_JSON}
                </pre>
              )}
              <textarea
                className="relative z-10 w-full min-h-[220px] p-3 bg-transparent text-sm font-mono leading-relaxed outline-none resize-y"
                value={jsonDraft}
                onChange={(e) => setJsonDraft(e.target.value)}
                onFocus={() => setJsonFocused(true)}
                onBlur={() => {
                  if (!jsonDraft.trim()) setJsonFocused(false);
                }}
                spellCheck={false}
              />
            </div>
            <p className="text-[11px] text-muted-foreground mt-2">
              Paste a single server object or a full <code className="text-rays-lilac">{"{ \"mcp_servers\": [...] }"}</code> block.
              On save, RAYS resolves <code className="text-rays-lilac">uvx</code> to your PATH and fills Blender env defaults.
            </p>

            <div className="flex flex-wrap gap-2 mt-3">
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={busy}
                className="px-3 py-1.5 rounded bg-rays-violet text-sm font-medium disabled:opacity-50"
              >
                Save MCP server
              </button>
              <button
                type="button"
                onClick={handleReloadMcp}
                disabled={busy || !sessionActive}
                className="px-3 py-1.5 rounded border text-sm inline-flex items-center gap-1.5 disabled:opacity-50"
                style={{ borderColor: "rgba(255,255,255,0.12)" }}
                title={sessionActive ? "Reconnect MCP without restarting the agent" : "Start an agent session first"}
              >
                <RefreshCw size={14} />
                Reload MCP
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
