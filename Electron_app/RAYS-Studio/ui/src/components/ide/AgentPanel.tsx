import { useEffect, useMemo, useRef, useState } from "react";
import { Send, Bot, User } from "lucide-react";
import { ThinkingIndicator } from "@/components/agent/ThinkingIndicator";
import { resolveThinkingDisplayPhase } from "@/components/agent/thinkingDisplay";
import type { ChatMessage, ThinkingPhase } from "@/services/raysSession";

type AgentPanelProps = {
  messages: ChatMessage[];
  connected: boolean;
  running: boolean;
  thinkingPhase?: ThinkingPhase;
  thinkingText?: string;
  onSend: (prompt: string) => void;
  onThinkingRevealComplete?: () => void;
};

export function AgentPanel({
  messages,
  connected,
  running,
  thinkingPhase = "hidden",
  thinkingText = "",
  onSend,
  onThinkingRevealComplete,
}: AgentPanelProps) {
  const [input, setInput] = useState("");
  const [streamedThinking, setStreamedThinking] = useState("");
  const messagesRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = useMemo(() => connected && input.trim().length > 0, [connected, input]);

  const visibleMessages = useMemo(
    () => messages.filter((msg) => msg.title !== "Thinking"),
    [messages]
  );

  const thinkingDisplayPhase = resolveThinkingDisplayPhase(thinkingPhase, running);
  const showThinking = thinkingDisplayPhase !== "hidden";

  const handleSend = () => {
    if (!canSend) return;
    onSend(input.trim());
    setInput("");
  };

  useEffect(() => {
    if (!messagesRef.current) return;
    messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
  }, [visibleMessages, running, thinkingPhase, streamedThinking]);

  useEffect(() => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = "0px";
    const next = Math.min(textareaRef.current.scrollHeight, 140);
    textareaRef.current.style.height = `${next}px`;
  }, [input]);

  useEffect(() => {
    if (thinkingPhase !== "streaming") {
      if (thinkingPhase === "active") setStreamedThinking("");
      return;
    }

    const full =
      thinkingText.trim() ||
      "Internal planning and orchestration completed for this request.";

    let index = 0;
    setStreamedThinking("");

    const tick = () => {
      index += Math.max(3, Math.ceil(full.length / 60));
      if (index >= full.length) {
        setStreamedThinking(full);
        window.setTimeout(() => onThinkingRevealComplete?.(), 400);
        return;
      }
      setStreamedThinking(full.slice(0, index));
      window.setTimeout(tick, 24);
    };

    const timer = window.setTimeout(tick, 120);
    return () => window.clearTimeout(timer);
  }, [thinkingPhase, thinkingText, onThinkingRevealComplete]);

  return (
    <div className="h-full flex flex-col bg-card">
      <div
        className="px-3 py-2 text-[10px] font-semibold tracking-widest uppercase text-muted-foreground border-b"
        style={{ borderColor: "rgba(255,255,255,0.05)" }}
      >
        Agent {connected ? "• connected" : "• disconnected"}
      </div>

      <div ref={messagesRef} className="flex-1 overflow-y-auto p-3 space-y-3">
        {visibleMessages.map((msg) => (
          <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div
              className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
                msg.role === "agent" ? "bg-rays-violet" : "bg-rays-mid"
              }`}
            >
              {msg.role === "agent" ? (
                <Bot size={13} className="text-accent-foreground" />
              ) : (
                <User size={13} className="text-accent-foreground" />
              )}
            </div>
            <div
              className={`max-w-[85%] px-3 py-2 rounded-lg text-ui border-rays-mid ${
                msg.role === "agent" ? "bg-secondary" : "bg-accent/20"
              }`}
              style={{ borderWidth: "1px", borderColor: "hsl(255 50% 60% / 0.15)" }}
            >
              {msg.title && (
                <div className="mb-1 text-[10px] uppercase tracking-widest text-muted-foreground">{msg.title}</div>
              )}
              <div className="whitespace-pre-wrap break-words">{msg.content}</div>
            </div>
          </div>
        ))}

        {showThinking && (
          <ThinkingIndicator
            phase={thinkingDisplayPhase}
            text={
              thinkingPhase === "streaming" || thinkingPhase === "done"
                ? streamedThinking || thinkingText
                : ""
            }
            label={running ? "Thinking" : "Reasoning"}
          />
        )}
      </div>

      <div className="p-2 border-t" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
        <div className="flex items-end gap-2">
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
            placeholder="Ask RAYS agent..."
            disabled={!connected}
            rows={1}
            className="flex-1 resize-none overflow-y-auto bg-secondary rounded-md px-3 py-2 text-ui text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-rays-pink"
          />
          <button
            onClick={handleSend}
            disabled={!canSend}
            className="p-1.5 rounded-md bg-rays-pink/20 hover:bg-rays-pink/30 text-rays-pink transition-colors active:scale-95"
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
