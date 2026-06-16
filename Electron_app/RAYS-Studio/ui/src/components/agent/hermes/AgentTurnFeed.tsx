import type { AgentTurn, ActivityItem } from "@/services/agentActivity";
import { formatDuration } from "@/services/agentActivity";
import { ThinkingDisclosure } from "./ThinkingDisclosure";
import { ActivityItemView } from "./ActivityRows";

function UserPromptBox({ text }: { text: string }) {
  return (
    <div
      className="rounded-lg border border-border/50 bg-card/30 px-4 py-3 text-sm leading-relaxed text-foreground/90"
      data-slot="user-prompt"
    >
      <span className="whitespace-pre-wrap break-words">{text}</span>
    </div>
  );
}

function FinalSummaryBlock({ content }: { content: string }) {
  return (
    <div className="mt-4 text-sm leading-relaxed text-foreground/90 whitespace-pre-wrap" data-slot="final-summary">
      {content}
    </div>
  );
}

function TurnActivityItems({ items }: { items: ActivityItem[] }) {
  const thinkingItems = items.filter((i): i is Extract<ActivityItem, { kind: "thinking" }> => i.kind === "thinking");
  const otherItems = items.filter((i) => i.kind !== "thinking");

  return (
    <div className="mt-3 space-y-2">
      {thinkingItems.map((item) => (
        <ThinkingDisclosure
          key={item.id}
          text={item.text}
          pending={item.status === "running"}
          durationMs={item.durationMs}
          timerKey={item.id}
        />
      ))}
      {otherItems.map((item) => (
        <ActivityItemView key={item.id} item={item} />
      ))}
    </div>
  );
}

function AgentTurnBlock({ turn, isLatest }: { turn: AgentTurn; isLatest: boolean }) {
  const showLiveThinking =
    isLatest &&
    turn.status === "running" &&
    !turn.items.some((i) => i.kind === "thinking") &&
    !turn.finalSummary;

  return (
    <div className="agent-turn py-6 border-b border-border/30 last:border-b-0">
      <UserPromptBox text={turn.userPrompt} />
      <TurnActivityItems items={turn.items} />
      {showLiveThinking && (
        <div className="mt-3">
          <ThinkingDisclosure
            text=""
            pending
            timerKey={`live-${turn.id}`}
          />
        </div>
      )}
      {turn.finalSummary && <FinalSummaryBlock content={turn.finalSummary} />}
      {turn.status === "done" && turn.endedAt && (
        <div className="mt-3 flex items-center gap-1.5 text-[0.625rem] text-muted-foreground/40 tabular-nums">
          <span className="inline-block size-3 rounded-sm bg-muted-foreground/20" aria-hidden />
          {formatDuration(turn.endedAt - turn.startedAt)}
        </div>
      )}
    </div>
  );
}

type AgentTurnFeedProps = {
  turns: AgentTurn[];
};

export function AgentTurnFeed({ turns }: AgentTurnFeedProps) {
  if (turns.length === 0) return null;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-2">
      {turns.map((turn, index) => (
        <AgentTurnBlock key={turn.id} turn={turn} isLatest={index === turns.length - 1} />
      ))}
    </div>
  );
}
