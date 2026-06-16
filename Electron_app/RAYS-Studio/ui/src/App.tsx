import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppShell } from "@/components/AppShell";
import IDELayout from "@/components/ide/IDELayout";
import AgentLayout from "@/components/agent/AgentLayout";
import NotFound from "./pages/NotFound.tsx";
import { useEffect } from "react";
import { syncInstallEpoch } from "@/services/appStorage";

const queryClient = new QueryClient();

async function ensureFreshInstallState(): Promise<void> {
  const desktop = window.raysDesktop;
  if (desktop?.getInstallEpoch) {
    const { epoch } = await desktop.getInstallEpoch();
    syncInstallEpoch(epoch);
    return;
  }
  // Browser dev mode: single stable epoch so reloads keep state.
  syncInstallEpoch("dev");
}

const App = () => {
  useEffect(() => {
    void ensureFreshInstallState();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <HashRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Navigate to="/agent" replace />} />
              <Route path="/agent" element={<AgentLayout />} />
              <Route path="/ide" element={<IDELayout />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </HashRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;
