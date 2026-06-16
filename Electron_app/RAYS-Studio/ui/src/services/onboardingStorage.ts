import { ONBOARDING_SESSION_KEY } from "./appStorage";

export function isOnboardingCompleteThisSession(): boolean {
  if (sessionStorage.getItem(ONBOARDING_SESSION_KEY) === "1") {
    return true;
  }
  // Legacy key from older builds
  return sessionStorage.getItem("rays-onboarding-complete") === "1";
}

export function markOnboardingCompleteThisSession(): void {
  sessionStorage.setItem(ONBOARDING_SESSION_KEY, "1");
  sessionStorage.removeItem("rays-onboarding-complete");
}
