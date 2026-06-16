import type { ReactNode } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export function DisclosureRow({
  children,
  open,
  onToggle,
  trailing,
  action,
}: {
  children: ReactNode;
  open: boolean;
  onToggle?: () => void;
  trailing?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="group/disclosure relative flex w-full min-w-0 max-w-full text-muted-foreground">
      <button
        type="button"
        aria-expanded={onToggle ? open : undefined}
        disabled={!onToggle}
        onClick={onToggle}
        className={cn(
          "flex min-w-0 max-w-fit items-start gap-1.5 text-left transition-colors",
          onToggle
            ? "hover:text-foreground focus-visible:text-foreground focus-visible:outline-none cursor-pointer"
            : "cursor-default"
        )}
      >
        <span className="flex min-w-0 flex-col gap-0.5">{children}</span>
        {onToggle && (
          <span
            className={cn(
              "flex h-[1.35rem] shrink-0 items-center justify-center transition-opacity duration-150",
              open
                ? "opacity-80"
                : "opacity-0 group-hover/disclosure:opacity-80 group-focus-within/disclosure:opacity-80"
            )}
          >
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>
        )}
      </button>
      {action && (
        <span className="ml-auto flex h-[1.35rem] shrink-0 items-center self-start pl-1.5">{action}</span>
      )}
      {trailing && (
        <span className="absolute right-1 top-0 flex h-[1.35rem] items-center tabular-nums text-[0.625rem]">
          {trailing}
        </span>
      )}
    </div>
  );
}
