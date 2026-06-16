import { useEffect, useRef, useState } from "react";
import type { TerminalLine } from "@/services/raysSession";

export function TerminalPanel({
  lines,
  connected,
  onSubmitInput,
}: {
  lines: TerminalLine[];
  connected: boolean;
  onSubmitInput: (input: string) => void;
}) {
  const [input, setInput] = useState("");
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!outputRef.current) return;
    outputRef.current.scrollTop = outputRef.current.scrollHeight;
  }, [lines]);

  const handleSubmit = () => {
    if (!input.trim()) return;
    onSubmitInput(input.trim());
    setInput("");
  };

  return (
    <div className="h-full flex flex-col bg-background font-mono-code text-code">
      <div className="flex items-center justify-between px-3 py-1.5 border-b" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
        <span className="text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">Terminal {connected ? "• live" : "• offline"}</span>
        <div className="flex gap-1">
          <span className="text-[10px] text-rays-mid px-1.5 py-0.5 rounded bg-secondary">bash</span>
        </div>
      </div>
      <div ref={outputRef} className="flex-1 overflow-y-auto p-3 space-y-0.5">
        {lines.length === 0 && <div className="text-muted-foreground">No output yet.</div>}
        {lines.map((line, i) => (
          <div key={i} className={
            line.kind === "command" ? "text-rays-lavender" :
            "text-foreground/70"
          }>
            {line.content}
          </div>
        ))}
      </div>
      <div className="px-3 py-2 border-t flex items-center gap-2" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
        <span className="text-rays-pink">$</span>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          disabled={!connected}
          className="flex-1 bg-transparent text-foreground focus:outline-none"
          placeholder="Enter command..."
        />
      </div>
    </div>
  );
}
