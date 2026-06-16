import { useEffect, useState } from "react";

export function useElapsedSeconds(active: boolean, resetKey?: string): number {
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (active) {
      setStartedAt(Date.now());
      setElapsed(0);
    } else {
      setStartedAt(null);
    }
  }, [active, resetKey]);

  useEffect(() => {
    if (!active || startedAt === null) return;
    const tick = () => setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [active, startedAt]);

  return elapsed;
}
