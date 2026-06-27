import { beforeEach, describe, expect, it } from "vitest";
import {
  conversationIdForWorkspace,
  loadProviderSettings,
  loadRecentWorkspaces,
  rememberWorkspace,
  removeRecentWorkspace,
  saveProviderSettings,
} from "./workspaceStorage";

describe("workspaceStorage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("loads default provider settings when empty", () => {
    const settings = loadProviderSettings();
    expect(settings.provider).toBe("ollama");
    expect(settings.model).toBeTruthy();
  });

  it("migrates legacy provider settings key", () => {
    localStorage.setItem(
      "rays-provider-settings",
      JSON.stringify({ provider: "gemini", model: "gemini-2.0-flash", apiKey: "k" })
    );

    const settings = loadProviderSettings();

    expect(settings.provider).toBe("gemini");
    expect(localStorage.getItem("rays-provider-settings")).toBeNull();
    expect(localStorage.getItem("rays-studio:provider-settings")).toBeTruthy();
  });

  it("rememberWorkspace deduplicates and caps recents", () => {
    for (let i = 0; i < 15; i++) {
      rememberWorkspace(`/tmp/project-${i}`);
    }
    const recents = loadRecentWorkspaces();
    expect(recents).toHaveLength(12);
    expect(recents[0]?.path).toBe("/tmp/project-14");
  });

  it("removeRecentWorkspace drops a path", () => {
    rememberWorkspace("/tmp/a");
    rememberWorkspace("/tmp/b");
    removeRecentWorkspace("/tmp/a");
    expect(loadRecentWorkspaces().map((w) => w.path)).toEqual(["/tmp/b"]);
  });

  it("conversationIdForWorkspace is stable for the same path", () => {
    const a = conversationIdForWorkspace("/home/user/repo");
    const b = conversationIdForWorkspace("/home/user/repo");
    expect(a).toBe(b);
    expect(a.startsWith("ws_")).toBe(true);
  });

  it("saveProviderSettings round-trips", () => {
    saveProviderSettings({ provider: "gemini", model: "m", apiKey: "secret" });
    expect(loadProviderSettings().apiKey).toBe("secret");
  });
});
