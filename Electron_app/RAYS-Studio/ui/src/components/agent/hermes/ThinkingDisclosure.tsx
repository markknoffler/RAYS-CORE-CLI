import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { formatDuration } from "@/services/agentActivity";
import { DisclosureRow } from "./DisclosureRow";
import { useElapsedSeconds } from "./useElapsedSeconds";

type ThinkingDisclosureProps = {
  text: string;
  pending: boolean;
  durationMs?: number;
  timerKey?: string;
};

export function ThinkingDisclosure({ text, pending, durationMs, timerKey }: ThinkingDisclosureProps) {
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const [displayText, setDisplayText] = useState("");
  const elapsed = useElapsedSeconds(pending, timerKey);
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  const open = userOpen ?? pending;
  const isPreview = pending && userOpen === null;

  useEffect(() => {
    if (!pending) {
      setDisplayText(text);
      return;
    }

    const full =
      text.trim() ||
      "Planning and reasoning about your request…";

    let index = 0;
    setDisplayText("");

    const tick = () => {
      index += Math.max(2, Math.ceil(full.length / 80));
      if (index >= full.length) {
        setDisplayText(full);
        return;
      }
      setDisplayText(full.slice(0, index));
      window.setTimeout(tick, 28);
    };

    const timer = window.setTimeout(tick, 80);
    return () => window.clearTimeout(timer);
  }, [pending, text, timerKey]);

  useEffect(() => {
    if (!isPreview) return;
    const el = scrollRef.current;
    const content = contentRef.current;
    if (!el || !content) return;

    const pin = () => {
      el.scrollTop = el.scrollHeight;
    };
    pin();
    const observer = new ResizeObserver(pin);
    observer.observe(content);
    return () => observer.disconnect();
  }, [isPreview, open, displayText]);

  const timerLabel = pending
    ? elapsed > 0
      ? `${elapsed}s`
      : undefined
    : durationMs
      ? formatDuration(durationMs)
      : undefined;

  return (
    <div className="agent-scaffolding text-[0.6875rem] leading-relaxed" data-slot="thinking-disclosure">
      <DisclosureRow onToggle={() => setUserOpen(!open)} open={open} trailing={!open ? timerLabel : undefined}>
        <span className="flex min-w-0 items-baseline gap-1.5">
          <span
            className={cn(
              "text-[0.6875rem] font-medium leading-[1.35rem] text-muted-foreground",
              pending && "hermes-shimmer text-foreground/70"
            )}
          >
            Thinking
          </span>
          {pending && timerLabel && (
            <span className="text-[0.625rem] tabular-nums text-muted-foreground/70">{timerLabel}</span>
          )}
        </span>
      </DisclosureRow>
      {open && displayText && (
        <div
          ref={scrollRef}
          className={cn(
            "mt-0.5 w-full min-w-0 max-w-full overflow-hidden wrap-anywhere pb-1 text-muted-foreground/80",
            isPreview && "thinking-preview max-h-40 overflow-y-auto"
          )}
        >
          <div ref={contentRef} className="whitespace-pre-wrap text-[0.6875rem] leading-relaxed">
            {displayText}
            {pending && <span className="thinking-cursor">▍</span>}
          </div>
        </div>
      )}
    </div>
  );
}
