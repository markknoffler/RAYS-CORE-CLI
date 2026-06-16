import { HelpCircle } from "lucide-react";

type ApprovalPanelProps = {
  message: string;
  onApprove: () => void;
  onDeny: () => void;
};

export function ApprovalPanel({ message, onApprove, onDeny }: ApprovalPanelProps) {
  return (
    <div className="clarify-shell relative mb-3 mt-2 rounded-lg border border-border/70 bg-card/40 text-sm shadow-panel">
      <span aria-hidden className="clarify-arc-border" />
      <div className="p-4 space-y-3">
        <div className="flex items-start gap-2">
          <HelpCircle size={16} className="mt-0.5 shrink-0 text-rays-lilac/80" />
          <p className="text-sm text-foreground/90 leading-relaxed">{message}</p>
        </div>
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onDeny}
            className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Deny
          </button>
          <button
            type="button"
            onClick={onApprove}
            className="px-4 py-1.5 rounded-md bg-rays-violet text-xs font-medium"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
