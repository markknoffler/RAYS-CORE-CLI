import { useState } from "react";
import { Terminal, HelpCircle, Wrench, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ActivityItem } from "@/services/agentActivity";
import { formatDuration } from "@/services/agentActivity";
import { DisclosureRow } from "./DisclosureRow";

function ActivityIcon({ item }: { item: ActivityItem }) {
  if (item.kind === "command") {
    return <Terminal size={14} className="text-muted-foreground/70" />;
  }
  if (item.kind === "question") {
    return <HelpCircle size={14} className="text-muted-foreground/70" />;
  }
  if (item.kind === "action") {
    return item.ok ? (
      <CheckCircle2 size={14} className="text-emerald-500/80" />
    ) : (
      <AlertCircle size={14} className="text-destructive/80" />
    );
  }
  if (item.kind === "tool") {
    if (item.status === "running") {
      return <Loader2 size={14} className="animate-spin text-muted-foreground/70" />;
    }
    return item.status === "error" ? (
      <AlertCircle size={14} className="text-destructive/80" />
    ) : (
      <Wrench size={14} className="text-muted-foreground/70" />
    );
  }
  return null;
}

function ActivityRowHeader({
  title,
  subtitle,
  pending,
  durationMs,
  icon,
}: {
  title: string;
  subtitle?: string;
  pending?: boolean;
  durationMs?: number;
  icon?: React.ReactNode;
}) {
  return (
    <span className="flex min-w-0 items-start gap-2">
      {icon && <span className="mt-0.5 grid size-3.5 shrink-0 place-items-center">{icon}</span>}
      <span className="flex min-w-0 flex-col gap-0.5">
        <span
          className={cn(
            "text-[0.6875rem] font-medium leading-[1.35rem] text-muted-foreground",
            pending && "hermes-shimmer"
          )}
        >
          {title}
        </span>
        {subtitle && (
          <span className="text-[0.625rem] leading-snug text-muted-foreground/60 line-clamp-1">{subtitle}</span>
        )}
      </span>
    </span>
  );
}

export function ToolActivityRow({ item }: { item: Extract<ActivityItem, { kind: "tool" }> }) {
  const [open, setOpen] = useState(false);
  const pending = item.status === "running";
  const duration = item.durationMs ? formatDuration(item.durationMs) : undefined;

  return (
    <div className="agent-scaffolding text-[0.6875rem]" data-slot="tool-activity">
      <DisclosureRow
        onToggle={item.detail ? () => setOpen(!open) : undefined}
        open={open}
        trailing={!open && duration ? duration : undefined}
      >
        <ActivityRowHeader
          title={item.title}
          subtitle={!open ? item.summary : undefined}
          pending={pending}
          durationMs={item.durationMs}
          icon={<ActivityIcon item={item} />}
        />
      </DisclosureRow>
      {open && item.detail && (
        <pre className="mt-1 max-h-64 overflow-auto rounded-md border border-border/40 bg-card/30 px-2.5 py-2 font-mono text-[0.65rem] leading-relaxed text-muted-foreground/80 whitespace-pre-wrap">
          {item.detail}
        </pre>
      )}
    </div>
  );
}

export function ActionActivityRow({ item }: { item: Extract<ActivityItem, { kind: "action" }> }) {
  const [open, setOpen] = useState(false);
  const duration = item.durationMs ? formatDuration(item.durationMs) : undefined;
  const title = item.verb;
  const expandable = item.detail.trim().length > 0;

  return (
    <div className="agent-scaffolding text-[0.6875rem]" data-slot="action-activity">
      <DisclosureRow
        onToggle={expandable ? () => setOpen(!open) : undefined}
        open={open}
        trailing={!open && duration ? duration : undefined}
      >
        <span className="flex min-w-0 items-start gap-2">
          <span className="mt-0.5 grid size-3.5 shrink-0 place-items-center">
            <ActivityIcon item={item} />
          </span>
          <span className="flex min-w-0 flex-col gap-0.5">
            <span
              className={cn(
                "font-medium leading-[1.35rem]",
                item.ok ? "text-muted-foreground" : "text-destructive/90"
              )}
            >
              {title}
            </span>
            {!open && item.detail && (
              <span className="text-[0.625rem] leading-snug text-muted-foreground/60 line-clamp-2">
                {item.detail}
              </span>
            )}
          </span>
        </span>
      </DisclosureRow>
      {open && item.detail && (
        <pre className="mt-1 max-h-48 overflow-auto rounded-md border border-border/40 bg-card/30 px-2.5 py-2 font-mono text-[0.65rem] leading-relaxed text-muted-foreground/80 whitespace-pre-wrap">
          {item.detail}
        </pre>
      )}
    </div>
  );
}

export function CommandActivityRow({ item }: { item: Extract<ActivityItem, { kind: "command" }> }) {
  const [open, setOpen] = useState(false);
  const pending = item.status === "running";
  const duration = item.durationMs ? formatDuration(item.durationMs) : undefined;
  const title = `Ran · ${item.command.length > 48 ? `${item.command.slice(0, 45)}…` : item.command}`;

  return (
    <div className="agent-scaffolding text-[0.6875rem]" data-slot="command-activity">
      <DisclosureRow
        onToggle={item.output ? () => setOpen(!open) : undefined}
        open={open}
        trailing={!open && duration ? duration : undefined}
      >
        <ActivityRowHeader
          title={title}
          pending={pending}
          icon={<ActivityIcon item={item} />}
        />
      </DisclosureRow>
      {open && item.output && (
        <pre className="mt-1 max-h-64 overflow-auto rounded-md border border-border/40 bg-card/30 px-2.5 py-2 font-mono text-[0.65rem] leading-relaxed text-muted-foreground/80 whitespace-pre-wrap">
          {item.output}
        </pre>
      )}
    </div>
  );
}

export function QuestionActivityRow({ item }: { item: Extract<ActivityItem, { kind: "question" }> }) {
  const duration = item.status === "pending" ? undefined : undefined;
  return (
    <div className="agent-scaffolding flex items-center gap-2 text-[0.6875rem] text-muted-foreground">
      <HelpCircle size={14} className="text-muted-foreground/70" />
      <span className="font-medium">Asked a question</span>
      {duration && <span className="tabular-nums text-[0.625rem]">{duration}</span>}
    </div>
  );
}

export function NoteActivityRow({ item }: { item: Extract<ActivityItem, { kind: "note" }> }) {
  const [open, setOpen] = useState(false);
  const expandable = item.message.length > 80;

  return (
    <div
      className={cn(
        "text-[0.6875rem] rounded-md",
        item.level === "warn" && "bg-amber-500/10 text-amber-200/80",
        item.level === "error" && "bg-destructive/10 text-destructive/90",
        item.level === "info" && "text-muted-foreground/70"
      )}
    >
      <DisclosureRow
        onToggle={expandable ? () => setOpen(!open) : undefined}
        open={open}
      >
        <span className={cn("px-2 py-1 block", !open && "line-clamp-3")}>{item.message}</span>
      </DisclosureRow>
      {open && (
        <pre className="mx-2 mb-2 max-h-48 overflow-auto rounded-md border border-border/40 bg-card/30 px-2.5 py-2 font-mono text-[0.65rem] leading-relaxed whitespace-pre-wrap">
          {item.message}
        </pre>
      )}
    </div>
  );
}

export function ActivityItemView({ item }: { item: ActivityItem }) {
  switch (item.kind) {
    case "tool":
      return <ToolActivityRow item={item} />;
    case "action":
      return <ActionActivityRow item={item} />;
    case "command":
      return <CommandActivityRow item={item} />;
    case "question":
      return <QuestionActivityRow item={item} />;
    case "note":
      return <NoteActivityRow item={item} />;
    default:
      return null;
  }
}
