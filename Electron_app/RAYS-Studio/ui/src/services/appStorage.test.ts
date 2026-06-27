import { beforeEach, describe, expect, it } from "vitest";
import {
  INSTALL_EPOCH_KEY,
  PROVIDER_SETTINGS_KEY,
  RECENT_WORKSPACES_KEY,
  clearAllAppStorage,
  syncInstallEpoch,
} from "./appStorage";

describe("appStorage", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("syncInstallEpoch clears storage when epoch changes", () => {
    localStorage.setItem(PROVIDER_SETTINGS_KEY, '{"provider":"ollama"}');
    localStorage.setItem(INSTALL_EPOCH_KEY, "epoch-a");

    const cleared = syncInstallEpoch("epoch-b");

    expect(cleared).toBe(true);
    expect(localStorage.getItem(PROVIDER_SETTINGS_KEY)).toBeNull();
    expect(localStorage.getItem(INSTALL_EPOCH_KEY)).toBe("epoch-b");
  });

  it("syncInstallEpoch is a no-op when epoch matches", () => {
    localStorage.setItem(INSTALL_EPOCH_KEY, "epoch-a");
    localStorage.setItem(RECENT_WORKSPACES_KEY, "[]");

    const cleared = syncInstallEpoch("epoch-a");

    expect(cleared).toBe(false);
    expect(localStorage.getItem(RECENT_WORKSPACES_KEY)).toBe("[]");
  });

  it("clearAllAppStorage removes rays-studio and legacy keys", () => {
    localStorage.setItem(PROVIDER_SETTINGS_KEY, "{}");
    localStorage.setItem("rays-user", "Alice");
    localStorage.setItem("unrelated", "keep");

    clearAllAppStorage();

    expect(localStorage.getItem(PROVIDER_SETTINGS_KEY)).toBeNull();
    expect(localStorage.getItem("rays-user")).toBeNull();
    expect(localStorage.getItem("unrelated")).toBe("keep");
  });
});
