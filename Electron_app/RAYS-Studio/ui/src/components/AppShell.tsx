import { useState, useCallback } from "react";
import { Outlet } from "react-router-dom";
import { OnboardingScreen } from "@/components/ide/OnboardingScreen";
import { USER_KEY } from "@/services/appStorage";
import {
  isOnboardingCompleteThisSession,
  markOnboardingCompleteThisSession,
} from "@/services/onboardingStorage";

export function AppShell() {
  const [showOnboarding, setShowOnboarding] = useState(
    () => !isOnboardingCompleteThisSession()
  );

  const handleOnboardingComplete = useCallback((name: string) => {
    localStorage.setItem(USER_KEY, name.trim() || "User");
    markOnboardingCompleteThisSession();
    setShowOnboarding(false);
  }, []);

  return (
    <>
      {showOnboarding && <OnboardingScreen onComplete={handleOnboardingComplete} />}
      {!showOnboarding && <Outlet />}
    </>
  );
}
