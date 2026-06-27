import { beforeEach, describe, expect, it } from "vitest";
import { ONBOARDING_SESSION_KEY } from "./appStorage";
import {
  isOnboardingCompleteThisSession,
  markOnboardingCompleteThisSession,
} from "./onboardingStorage";

describe("onboardingStorage", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("starts incomplete for a fresh session", () => {
    expect(isOnboardingCompleteThisSession()).toBe(false);
  });

  it("marks onboarding complete for the session", () => {
    markOnboardingCompleteThisSession();
    expect(sessionStorage.getItem(ONBOARDING_SESSION_KEY)).toBe("1");
    expect(isOnboardingCompleteThisSession()).toBe(true);
  });

  it("treats legacy session key as complete", () => {
    sessionStorage.setItem("rays-onboarding-complete", "1");
    expect(isOnboardingCompleteThisSession()).toBe(true);
  });
});
