import { useState } from "react";
import { HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type ClarifyPromptPanelProps = {
  question: string;
  onSubmit: (answer: string) => void;
  onSkip: () => void;
};

export function ClarifyPromptPanel({ question, onSubmit, onSkip }: ClarifyPromptPanelProps) {
  const [draft, setDraft] = useState("");

  const handleSubmit = () => {
    const answer = draft.trim();
    if (!answer) return;
    onSubmit(answer);
    setDraft("");
  };

  return (
    <div className="clarify-shell relative mb-3 mt-2 rounded-lg border border-border/70 bg-card/40 text-sm shadow-panel">
      <span aria-hidden className="clarify-arc-border" />
      <div className="p-4 space-y-3">
        <div className="flex items-start gap-2">
          <HelpCircle size={16} className="mt-0.5 shrink-0 text-rays-lilac/80" />
          <p className="text-sm text-foreground/90 leading-relaxed">{question}</p>
        </div>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder="Type your answer…"
          rows={3}
          className={cn(
            "w-full resize-y rounded-md border border-border/50 bg-background/50 px-3 py-2",
            "text-sm outline-none placeholder:text-muted-foreground/50",
            "focus:border-rays-lilac/40 focus:ring-1 focus:ring-rays-lilac/20"
          )}
        />
        <div className="flex items-center justify-between gap-2">
          <span className="text-[0.625rem] text-muted-foreground/60">⌘/Ctrl + Enter to send</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onSkip}
              className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Skip
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!draft.trim()}
              className="px-4 py-1.5 rounded-md bg-secondary text-xs font-medium disabled:opacity-40 hover:bg-secondary/80 transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
