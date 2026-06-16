export function StatusBar() {
  return (
    <div className="h-[22px] bg-rays-violet flex items-center justify-between px-3 text-[10px] text-accent-foreground select-none">
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-diff-add pulse-glow" />
          Live
        </span>
        <span>main</span>
      </div>
      <div className="flex items-center gap-3">
        <span>RAYS Agent: Online</span>
        <span>UTF-8</span>
        <span>LF</span>
        <span>Spaces: 4</span>
      </div>
    </div>
  );
}
