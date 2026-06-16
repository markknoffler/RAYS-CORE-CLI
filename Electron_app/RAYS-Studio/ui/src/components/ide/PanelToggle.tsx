import { PanelLeft, Terminal, Bot } from "lucide-react";

type Props = {
  showExplorer: boolean;
  showAgent: boolean;
  showTerminal: boolean;
  onToggleExplorer: () => void;
  onToggleAgent: () => void;
  onToggleTerminal: () => void;
};

export function PanelToggle({ showExplorer, showAgent, showTerminal, onToggleExplorer, onToggleAgent, onToggleTerminal }: Props) {
  const btnClass = (active: boolean) =>
    `p-1.5 rounded transition-colors ${active ? "bg-rays-violet/30 text-rays-lavender" : "text-muted-foreground hover:text-foreground hover:bg-secondary"}`;

  return (
    <div className="flex items-center gap-0.5">
      <button className={btnClass(showExplorer)} onClick={onToggleExplorer} title="Toggle Explorer">
        <PanelLeft size={15} />
      </button>
      <button className={btnClass(showTerminal)} onClick={onToggleTerminal} title="Toggle Terminal">
        <Terminal size={15} />
      </button>
      <button className={btnClass(showAgent)} onClick={onToggleAgent} title="Toggle Agent">
        <Bot size={15} />
      </button>
    </div>
  );
}
