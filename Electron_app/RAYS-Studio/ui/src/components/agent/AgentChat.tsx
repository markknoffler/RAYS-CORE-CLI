import { useEffect, useMemo, useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { AgentTurnFeed } from "@/components/agent/hermes/AgentTurnFeed";
import { ApprovalPanel } from "@/components/agent/hermes/ApprovalPanel";
import type { AgentTurn } from "@/services/agentActivity";
import type { PromptMode } from "@/services/raysSession";

type AgentChatProps = {
  turns: AgentTurn[];
  connected: boolean;
  running: boolean;
  loading?: boolean;
  hudPhase?: string;
  hudDetail?: string;
  tokenCount?: number;
  pendingApproval?: { id: string; message: string } | null;
  defaultMode?: PromptMode;
  onSend: (prompt: string, mode?: PromptMode) => void;
  onApprove?: (approved: boolean) => void;
};

export function AgentChat({
  turns,
  connected,
  running,
  loading = false,
  hudPhase,
  hudDetail,
  tokenCount = 0,
  pendingApproval,
  defaultMode = "agent",
  onSend,
  onApprove,
}: AgentChatProps) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = useMemo(() => connected && input.trim().length > 0 && !running, [connected, input, running]);

  const handleSend = () => {
    if (!canSend) return;
    const text = input.trim();
    let mode = defaultMode;
    if (text.startsWith("/code")) mode = "code";
    else if (text.startsWith("/chat")) mode = "chat";
    onSend(text, mode);
    setInput("");
  };

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [turns, running, pendingApproval]);

  useEffect(() => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = "0px";
    const next = Math.min(textareaRef.current.scrollHeight, 160);
    textareaRef.current.style.height = `${next}px`;
  }, [input]);

  const showEmpty = turns.length === 0 && !running;

  return (
    <div className="h-full flex flex-col bg-background agent-chat-shell">
      <div
        className="px-4 py-2 border-b flex items-center justify-between gap-2 shrink-0"
        style={{ borderColor: "rgba(255,255,255,0.05)" }}
      >
        <div className="min-w-0">
          <div className="text-sm font-medium truncate">
            {loading ? "Loading chat…" : hudPhase || (connected ? "Ready" : "Connecting…")}
          </div>
          {hudDetail && <div className="text-[11px] text-muted-foreground truncate">{hudDetail}</div>}
        </div>
        <div className="text-[10px] text-muted-foreground shrink-0">
          {tokenCount > 0 ? `${tokenCount.toLocaleString()} tokens` : connected ? "Connected" : "Offline"}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto min-h-0">
        {showEmpty && (
          <div className="text-center text-muted-foreground text-sm py-16 px-6">
            <Sparkles className="mx-auto mb-3 text-rays-lilac" size={28} />
            <p className="text-foreground/80">Ask the agent anything about this workspace.</p>
            <p className="text-xs mt-2 text-muted-foreground/70">
              Use /code for coding pipeline, /chat for chat mode, /mcp for MCP status.
            </p>
          </div>
        )}

        <AgentTurnFeed turns={turns} />

        {pendingApproval && (
          <div className="mx-auto max-w-3xl px-4 pb-4">
            <ApprovalPanel
              message={pendingApproval.message}
              onApprove={() => onApprove?.(true)}
              onDeny={() => onApprove?.(false)}
            />
          </div>
        )}
      </div>

      <div className="p-3 border-t shrink-0" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
        <div
          className="mx-auto max-w-3xl flex items-end gap-2 rounded-xl border bg-card/40 px-3 py-2"
          style={{ borderColor: "rgba(255,255,255,0.08)" }}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Send a message… (/code, /chat, /mcp)"
            rows={1}
            className="flex-1 bg-transparent resize-none text-sm outline-none placeholder:text-muted-foreground max-h-40"
            disabled={!connected || loading}
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={!canSend}
            className="p-2 rounded-full bg-rays-violet text-accent-foreground disabled:opacity-40 transition-opacity shrink-0"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
