import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

type ThinkingIndicatorProps = {
  /** active = in-flight planning; streaming = reveal after response; done = collapsed summary */
  phase: "active" | "streaming" | "done" | "hidden";
  text: string;
  label?: string;
};

export function ThinkingIndicator({ phase, text, label = "Thinking" }: ThinkingIndicatorProps) {
  const [expanded, setExpanded] = useState(true);

  if (phase === "hidden") return null;

  const displayText =
    text.trim() ||
    (phase === "active"
      ? "Planning and reasoning about your request…"
      : "Internal planning and orchestration completed.");

  const isAnimating = phase === "active" || phase === "streaming";

  return (
    <div className="flex gap-2.5 w-full">
      <div className="w-7 h-7 rounded-full shrink-0 thinking-orb flex items-center justify-center">
        <span className="thinking-orb-core" />
      </div>
      <div className="flex-1 min-w-0 rounded-lg border overflow-hidden thinking-panel">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="w-full flex items-center gap-2 px-3 py-2 text-left text-xs uppercase tracking-widest text-muted-foreground hover:bg-secondary/40 transition-colors"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span className={isAnimating ? "thinking-label-active" : ""}>{label}</span>
          {isAnimating && <span className="thinking-light-sweep ml-auto" aria-hidden />}
        </button>
        {expanded && (
          <div className={`px-3 pb-3 text-sm text-muted-foreground relative ${isAnimating ? "thinking-text-reveal" : ""}`}>
            <div className="whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed">{displayText}</div>
          </div>
        )}
      </div>
    </div>
  );
}
