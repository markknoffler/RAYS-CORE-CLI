import type { ThinkingPhase } from "@/services/raysSession";

export function resolveThinkingDisplayPhase(
  thinkingPhase: ThinkingPhase,
  running: boolean
): "active" | "streaming" | "done" | "hidden" {
  if (thinkingPhase === "streaming") return "streaming";
  if (thinkingPhase === "done") return "done";
  if (thinkingPhase === "active" || running) return "active";
  return "hidden";
}
