import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  loadProviderSettings,
  saveProviderSettings,
  type StoredProviderSettings,
} from "@/services/workspaceStorage";

const categories = ["AI Providers", "API Keys", "MCP Config"];

const providers: { id: StoredProviderSettings["provider"]; label: string }[] = [
  { id: "ollama", label: "Ollama (Local)" },
  { id: "gemini", label: "Google Gemini" },
  { id: "openai", label: "OpenAI" },
];

export function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [activeCategory, setActiveCategory] = useState("AI Providers");
  const [provider, setProvider] = useState<StoredProviderSettings["provider"]>("ollama");
  const [model, setModel] = useState("qwen3-coder:30b");
  const [apiKey, setApiKey] = useState("");
  const [savedHint, setSavedHint] = useState<string | null>(null);
  const [mcpConfig, setMcpConfig] = useState(`{
  "servers": [],
  "tools": [],
  "defaultTimeout": 30000
}`);

  useEffect(() => {
    if (!open) return;
    const s = loadProviderSettings();
    setProvider(s.provider);
    setModel(s.model);
    setApiKey(s.apiKey || "");
    setSavedHint(null);
  }, [open]);

  const persistProvider = () => {
    saveProviderSettings({ provider, model: model.trim(), apiKey: apiKey.trim() });
    setSavedHint("Saved. Applies the next time you open a workspace.");
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="w-[640px] max-h-[500px] bg-card rounded-lg shadow-modal overflow-hidden flex"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="w-[180px] bg-secondary/50 py-4 space-y-0.5">
              <div className="px-4 pb-3 text-heading font-bold text-rays-pink">Settings</div>
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={`w-full text-left px-4 py-1.5 text-ui transition-colors ${activeCategory === cat ? "bg-accent text-accent-foreground border-l-2 border-rays-pink" : "text-foreground/60 hover:text-foreground hover:bg-secondary"}`}
                >
                  {cat}
                </button>
              ))}
            </div>

            <div className="flex-1 p-5 overflow-y-auto">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-sm font-semibold text-foreground">{activeCategory}</h2>
                <button
                  onClick={onClose}
                  className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X size={16} />
                </button>
              </div>

              {activeCategory === "AI Providers" && (
                <div className="space-y-3">
                  <p className="text-ui text-muted-foreground mb-3">
                    Default provider and model for new workspace sessions.
                  </p>
                  <div className="flex gap-1 bg-secondary rounded-lg p-0.5">
                    {providers.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => setProvider(p.id)}
                        className={`flex-1 px-2 py-1.5 rounded-md text-ui transition-all ${provider === p.id ? "bg-rays-violet text-accent-foreground shadow-sm" : "text-foreground/60 hover:text-foreground"}`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                  <div className="space-y-2">
                    <label className="text-ui font-medium text-foreground/80">Model</label>
                    <input
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder={
                        provider === "ollama"
                          ? "qwen2.5-coder:latest"
                          : provider === "gemini"
                            ? "gemini-1.5-flash"
                            : "gpt-4o"
                      }
                      className="w-full bg-secondary rounded-md px-3 py-2 text-ui text-foreground focus:outline-none focus:ring-1 focus:ring-rays-pink"
                    />
                  </div>
                  {provider !== "ollama" && (
                    <div className="space-y-2">
                      <label className="text-ui font-medium text-foreground/80">API Key</label>
                      <input
                        type="password"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        className="w-full bg-secondary rounded-md px-3 py-2 text-ui text-foreground focus:outline-none focus:ring-1 focus:ring-rays-pink"
                      />
                    </div>
                  )}
                  <button
                    onClick={persistProvider}
                    className="mt-2 px-4 py-1.5 rounded-md bg-rays-pink/20 text-rays-pink text-ui font-medium hover:bg-rays-pink/30 transition-colors"
                  >
                    Save
                  </button>
                  {savedHint && <p className="text-xs text-muted-foreground">{savedHint}</p>}
                </div>
              )}

              {activeCategory === "API Keys" && (
                <div className="space-y-4">
                  <p className="text-ui text-muted-foreground">
                    API keys are stored locally and used for the provider selected above.
                  </p>
                  <div>
                    <label className="text-ui font-medium text-foreground/80 block mb-1">API Key</label>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="Enter API key…"
                      className="w-full bg-secondary rounded-md px-3 py-2 text-ui text-foreground focus:outline-none focus:ring-1 focus:ring-rays-pink"
                    />
                  </div>
                  <button
                    onClick={persistProvider}
                    className="px-4 py-1.5 rounded-md bg-rays-pink/20 text-rays-pink text-ui font-medium hover:bg-rays-pink/30 transition-colors"
                  >
                    Save Keys
                  </button>
                </div>
              )}

              {activeCategory === "MCP Config" && (
                <div className="space-y-3">
                  <p className="text-ui text-muted-foreground">Model Context Protocol configuration (JSON)</p>
                  <textarea
                    value={mcpConfig}
                    onChange={(e) => setMcpConfig(e.target.value)}
                    className="w-full h-[240px] bg-secondary rounded-md p-3 font-mono-code text-code text-foreground focus:outline-none focus:ring-1 focus:ring-rays-pink resize-none"
                    spellCheck={false}
                  />
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
