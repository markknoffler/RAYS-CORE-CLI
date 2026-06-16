export type ActivityItemStatus = "running" | "done" | "error";

export type ActivityItem =
  | {
      kind: "thinking";
      id: string;
      text: string;
      status: ActivityItemStatus;
      startedAt: number;
      durationMs?: number;
    }
  | {
      kind: "tool";
      id: string;
      server?: string;
      tool: string;
      title: string;
      summary: string;
      detail: string;
      status: ActivityItemStatus;
      startedAt: number;
      durationMs?: number;
    }
  | {
      kind: "action";
      id: string;
      verb: string;
      detail: string;
      ok: boolean;
      status: ActivityItemStatus;
      startedAt: number;
      durationMs?: number;
    }
  | {
      kind: "command";
      id: string;
      command: string;
      status: ActivityItemStatus;
      startedAt: number;
      durationMs?: number;
      output?: string;
    }
  | {
      kind: "question";
      id: string;
      question: string;
      status: "pending" | "done" | "skipped";
    }
  | {
      kind: "note";
      id: string;
      level: "info" | "warn" | "error";
      message: string;
    };

export type AgentTurn = {
  id: string;
  userPrompt: string;
  items: ActivityItem[];
  finalSummary?: string;
  status: "running" | "done";
  startedAt: number;
  endedAt?: number;
};

export function createTurn(userPrompt: string): AgentTurn {
  return {
    id: crypto.randomUUID(),
    userPrompt,
    items: [],
    status: "running",
    startedAt: Date.now(),
  };
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.max(1, Math.round(ms))}ms`;
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rem = seconds % 60;
  return `${minutes}:${String(rem).padStart(2, "0")}`;
}

function titleCaseTool(name: string): string {
  return name
    .split(/[_/]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function tryParseJson(raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

export function summarizeToolResult(
  server: string | undefined,
  tool: string,
  result: string
): { title: string; summary: string; detail: string } {
  const label = server ? `${server}/${tool}` : tool;
  const parsed = tryParseJson(result);

  if (parsed && typeof parsed === "object" && parsed !== null) {
    const obj = parsed as Record<string, unknown>;
    if ("object_count" in obj && typeof obj.object_count === "number") {
      const count = obj.object_count;
      const name = typeof obj.name === "string" ? obj.name : "scene";
      return {
        title: `Ran · ${label}`,
        summary: `Read ${name} (${count} object${count === 1 ? "" : "s"})`,
        detail: result,
      };
    }
    if ("objects" in obj && Array.isArray(obj.objects)) {
      const names = obj.objects
        .slice(0, 4)
        .map((o) => (typeof o === "object" && o && "name" in o ? String((o as { name: unknown }).name) : ""))
        .filter(Boolean);
      const suffix = obj.objects.length > 4 ? ` +${obj.objects.length - 4} more` : "";
      return {
        title: `Ran · ${label}`,
        summary: names.length ? `Found ${names.join(", ")}${suffix}` : `Returned ${obj.objects.length} objects`,
        detail: result,
      };
    }
    if ("success" in obj) {
      const ok = Boolean(obj.success);
      const msg = typeof obj.message === "string" ? obj.message : typeof obj.error === "string" ? obj.error : "";
      return {
        title: `Ran · ${label}`,
        summary: msg || (ok ? "Completed successfully" : "Failed"),
        detail: result,
      };
    }
    const keys = Object.keys(obj);
    if (keys.length <= 4) {
      const preview = keys.map((k) => `${k}: ${String(obj[k]).slice(0, 40)}`).join(", ");
      return {
        title: `Ran · ${label}`,
        summary: preview.slice(0, 120) || "Completed",
        detail: result,
      };
    }
  }

  const oneLine = result.replace(/\s+/g, " ").trim();
  if (oneLine.length <= 100) {
    return {
      title: `Ran · ${label}`,
      summary: oneLine || "Completed",
      detail: result,
    };
  }

  return {
    title: `Ran · ${titleCaseTool(tool)}`,
    summary: `${oneLine.slice(0, 96)}…`,
    detail: result,
  };
}

export function summarizeAction(verb: string, detail: string, ok: boolean): string {
  const base = detail.trim() || verb;
  if (base.length <= 80) return ok ? base : `${base} (failed)`;
  return `${base.slice(0, 77)}…${ok ? "" : " (failed)"}`;
}
