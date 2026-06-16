import { useState, useRef, useEffect } from "react";

const menuItems: Record<string, string[]> = {
  File: [
    "New File", "New Window", "---", "Open File...", "Open Folder...", "Open Recent", "---",
    "Save", "Save As...", "Save All", "---", "Auto Save", "Preferences", "---", "Close Editor", "Close Window"
  ],
  Edit: [
    "Undo", "Redo", "---", "Cut", "Copy", "Paste", "---",
    "Find", "Replace", "---", "Find in Files", "Replace in Files", "---",
    "Toggle Line Comment", "Toggle Block Comment", "---", "Emmet: Expand Abbreviation"
  ],
  Selection: [
    "Select All", "Expand Selection", "Shrink Selection", "---",
    "Copy Line Up", "Copy Line Down", "Move Line Up", "Move Line Down", "---",
    "Add Cursor Above", "Add Cursor Below", "Add Cursors to Line Ends", "---",
    "Select All Occurrences"
  ],
  View: [
    "Command Palette...", "---", "Explorer", "Search", "Source Control", "Run & Debug", "Extensions", "---",
    "Terminal", "Problems", "Output", "Debug Console", "---",
    "Word Wrap", "Minimap", "Breadcrumbs", "---", "Zoom In", "Zoom Out", "Reset Zoom"
  ],
  Go: [
    "Back", "Forward", "---", "Go to File...", "Go to Symbol in Workspace...", "---",
    "Go to Symbol in Editor...", "Go to Definition", "Go to Declaration", "Go to Type Definition", "---",
    "Go to Line/Column...", "Go to Bracket", "---", "Next Problem", "Previous Problem"
  ],
  Run: [
    "Start Debugging", "Run Without Debugging", "Stop Debugging", "Restart Debugging", "---",
    "Open Configurations", "Add Configuration...", "---",
    "Step Over", "Step Into", "Step Out", "Continue", "---",
    "Toggle Breakpoint", "New Breakpoint", "---", "Run RAYS Agent"
  ],
  Terminal: [
    "New Terminal", "Split Terminal", "---", "Run Task...", "Run Build Task...", "---",
    "Run Active File", "Run Selected Text", "---", "Kill Terminal", "Clear Terminal"
  ],
  Help: [
    "Welcome", "Getting Started", "---", "Documentation", "Release Notes", "---",
    "Keyboard Shortcuts Reference", "---", "Report Issue", "---", "About RAYS"
  ],
};

export function TaskBar({ onOpenSettings }: { onOpenSettings: () => void }) {
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (barRef.current && !barRef.current.contains(e.target as Node)) {
        setActiveMenu(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={barRef} className="h-[38px] bg-card flex items-center px-3 gap-0 select-none text-ui border-b border-rays-mid" style={{ borderBottomWidth: '1px', borderBottomColor: 'rgba(255,255,255,0.05)' }}>
      {/* Brand */}
      <span className="font-extrabold tracking-wider text-sm mr-5 text-rays-pink">RAYS</span>

      {Object.entries(menuItems).map(([label, items]) => (
        <div key={label} className="relative">
          <button
            className={`px-3 py-1 rounded-sm transition-colors text-foreground/80 hover:text-foreground hover:bg-secondary ${activeMenu === label ? 'bg-secondary text-foreground' : ''}`}
            onClick={() => setActiveMenu(activeMenu === label ? null : label)}
            onMouseEnter={() => activeMenu && setActiveMenu(label)}
          >
            {label}
          </button>
          {activeMenu === label && (
            <div className="absolute top-full left-0 mt-0.5 min-w-[220px] bg-popover border border-border rounded-md shadow-modal py-1 z-50 animate-scale-in">
              {items.map((item, i) =>
                item === "---" ? (
                  <div key={i} className="h-px bg-border mx-2 my-1" />
                ) : (
                  <button
                    key={i}
                    className="w-full text-left px-3 py-1.5 text-ui text-foreground/80 hover:bg-accent hover:text-accent-foreground transition-colors"
                    onClick={() => {
                      if (item === "Preferences") onOpenSettings();
                      setActiveMenu(null);
                    }}
                  >
                    {item}
                  </button>
                )
              )}
            </div>
          )}
        </div>
      ))}

      <div className="flex-1" />

      {/* Settings gear */}
      <button onClick={onOpenSettings} className="p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors" title="Settings">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
      </button>
    </div>
  );
}
