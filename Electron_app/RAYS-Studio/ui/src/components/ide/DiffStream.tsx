import { motion } from "framer-motion";
import type { DiffChunk } from "@/services/raysSession";

export function DiffStream({ connected, chunks }: { connected: boolean; chunks: DiffChunk[] }) {
  return (
    <div className="h-full overflow-y-auto bg-background p-4 space-y-4">
      {/* Live indicator */}
      <div className="flex items-center gap-2 mb-2">
        <span className="w-2 h-2 rounded-full bg-diff-add pulse-glow" />
        <span className="text-ui text-muted-foreground">{connected ? "Live — WebSocket connected" : "Waiting for backend connection"}</span>
      </div>

      {chunks.length === 0 && <div className="text-sm text-muted-foreground">No diffs streamed yet.</div>}
      {chunks.map((chunk, ci) => (
        <motion.div
          key={chunk.id}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: ci * 0.15, duration: 0.35 }}
          className="rounded-lg overflow-hidden shadow-panel"
        >
          {/* Header */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-card">
            <span className={`w-2 h-2 rounded-full ${chunk.added > 0 ? "bg-rays-pink" : "bg-diff-remove"}`} />
            <span className="text-ui font-semibold text-foreground">
              {chunk.added > 0 ? "Write" : "Update"}(
              <span className="text-rays-lavender">{chunk.filePath}</span>)
            </span>
          </div>
          {chunk.added > 0 && (
            <div className="px-3 py-1 text-ui bg-card/50">
              <span className="text-rays-pink">↳ Added {chunk.added} lines, removed {chunk.removed} lines</span>
            </div>
          )}

          {/* Code lines */}
          <div className="font-mono-code text-code">
            {chunk.lines.map((line, index) => (
              <div
                key={`${chunk.id}-${index}`}
                className={`flex ${line.type === "add" ? "bg-diff-add" : "bg-diff-remove"}`}
              >
                <span className="w-10 text-right pr-2 select-none text-muted-foreground/50 shrink-0">
                  {index + 1}
                </span>
                <span className={`pr-4 ${line.type === "add" ? "text-diff-add" : "text-diff-remove"}`}>
                  {line.type === "add" ? "+ " : "- "}
                  {line.content}
                </span>
              </div>
            ))}
          </div>

          {/* Expand hint */}
          <div className="px-3 py-1 text-[10px] text-muted-foreground bg-card/30">
            … reason: {chunk.reason || "streamed update"}
          </div>
        </motion.div>
      ))}
    </div>
  );
}
