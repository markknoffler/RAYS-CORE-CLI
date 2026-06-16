import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

type Phase = "brand" | "name" | "greeting" | "done";

const BG = "hsl(265, 30%, 6%)";
const TEXT_PRIMARY = "hsl(270, 70%, 85%)";
const TEXT_SECONDARY = "hsl(260, 60%, 75%)";
const ACCENT = "hsl(330, 100%, 70%)";
const INPUT_BG = "hsl(265, 25%, 12%)";

export function OnboardingScreen({ onComplete }: { onComplete: (name: string) => void }) {
  const [phase, setPhase] = useState<Phase>("brand");
  const [name, setName] = useState("");
  const [typed1, setTyped1] = useState("");
  const [typed2, setTyped2] = useState("");
  const [showCursor1, setShowCursor1] = useState(true);
  const [showCursor2, setShowCursor2] = useState(false);

  useEffect(() => {
    if (phase === "brand") {
      const timer = setTimeout(() => setPhase("name"), 2800);
      return () => clearTimeout(timer);
    }
  }, [phase]);

  const startGreeting = useCallback(() => {
    const displayName = name.trim() || "there";
    const line1 = "Good morning RAYS";
    const line2 = `RAYS: Good morning ${displayName}, what can I do for you today?`;
    let i = 0;

    const type1 = setInterval(() => {
      if (i < line1.length) {
        setTyped1(line1.slice(0, i + 1));
        i++;
      } else {
        clearInterval(type1);
        setShowCursor1(false);
        setShowCursor2(true);
        let j = 0;
        const type2 = setInterval(() => {
          if (j < line2.length) {
            setTyped2(line2.slice(0, j + 1));
            j++;
          } else {
            clearInterval(type2);
            setTimeout(() => {
              setShowCursor2(false);
              setTimeout(() => setPhase("done"), 1200);
            }, 800);
          }
        }, 35);
      }
    }, 40);
  }, [name]);

  useEffect(() => {
    if (phase === "greeting") startGreeting();
  }, [phase, startGreeting]);

  useEffect(() => {
    if (phase === "done") {
      onComplete(name.trim() || "User");
    }
  }, [phase, name, onComplete]);

  const handleNameSubmit = () => {
    if (name.trim()) setPhase("greeting");
  };

  const raysPath =
    "M 8 40 L 8 10 L 22 10 Q 32 10 32 20 Q 32 28 22 28 L 15 28 L 33 40 " +
    "M 42 40 L 52 10 L 62 40 M 46 28 L 58 28 " +
    "M 72 10 L 82 25 L 92 10 M 82 25 L 82 40 " +
    "M 104 40 C 94 40 88 35 88 29 C 88 24 93 21 102 19 C 112 17 118 14 118 10 C 118 6 113 10 104 10";

  return (
    <AnimatePresence mode="wait">
      {phase !== "done" && (
        <motion.div
          key="onboarding"
          className="fixed inset-0 z-[100] flex items-center justify-center"
          style={{ backgroundColor: BG }}
        >
          {phase === "brand" && (
            <motion.div
              key="brand"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.5 }}
              className="flex flex-col items-center"
            >
              <svg width="260" height="60" viewBox="0 0 130 50" className="overflow-visible">
                <motion.path
                  d={raysPath}
                  fill="none"
                  stroke={ACCENT}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 1.8, ease: "easeInOut" }}
                />
              </svg>
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.5, duration: 0.5 }}
                className="mt-6 text-ui tracking-[0.3em] uppercase"
                style={{ color: TEXT_SECONDARY }}
              >
                AI-Native Code Editor
              </motion.div>
            </motion.div>
          )}

          {phase === "name" && (
            <motion.div
              key="name"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="flex flex-col items-center gap-5"
            >
              <h2 className="text-heading font-bold" style={{ color: TEXT_PRIMARY }}>
                What&apos;s your name?
              </h2>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleNameSubmit()}
                autoFocus
                className="w-64 text-center px-4 py-2 rounded-md text-sm font-mono focus:outline-none focus:ring-2"
                style={{
                  backgroundColor: INPUT_BG,
                  color: TEXT_PRIMARY,
                  caretColor: ACCENT,
                  borderWidth: "1px",
                  borderColor: "hsl(255, 50%, 60%, 0.3)",
                }}
                placeholder="Enter your name..."
              />
              <button
                onClick={handleNameSubmit}
                disabled={!name.trim()}
                className="px-6 py-2 rounded-md text-ui font-semibold transition-all active:scale-95 disabled:opacity-40"
                style={{ backgroundColor: ACCENT, color: BG }}
              >
                Continue
              </button>
            </motion.div>
          )}

          {phase === "greeting" && (
            <motion.div
              key="greeting"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="font-mono-code text-code max-w-lg w-full px-6"
            >
              <div className="flex items-start justify-center text-center" style={{ color: TEXT_SECONDARY }}>
                <span className="mr-2 shrink-0" style={{ color: ACCENT }}>
                  &gt;
                </span>
                <span>
                  {typed1}
                  {showCursor1 && (
                    <span
                      className="inline-block w-[2px] h-4 ml-0.5 animate-pulse"
                      style={{ backgroundColor: ACCENT }}
                    />
                  )}
                </span>
              </div>
              {typed2 && (
                <div
                  className="mt-3 flex items-start justify-center text-center"
                  style={{ color: TEXT_PRIMARY }}
                >
                  <span className="mr-2 shrink-0" style={{ color: ACCENT }}>
                    &gt;
                  </span>
                  <span>
                    {typed2}
                    {showCursor2 && (
                      <span
                        className="inline-block w-[2px] h-4 ml-0.5 animate-pulse"
                        style={{ backgroundColor: ACCENT }}
                      />
                    )}
                  </span>
                </div>
              )}
            </motion.div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
