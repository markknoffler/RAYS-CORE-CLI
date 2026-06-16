/** Keys and helpers for renderer-local persistence (localStorage / sessionStorage). */

export const INSTALL_EPOCH_KEY = "rays-studio:install-epoch";
export const USER_KEY = "rays-studio:user";
export const RECENT_WORKSPACES_KEY = "rays-studio:recent-workspaces";
export const PROVIDER_SETTINGS_KEY = "rays-studio:provider-settings";
export const AGENT_SIDEBAR_WIDTH_KEY = "rays-studio:agent-sidebar-width";
export const AGENT_EXPLORER_WIDTH_KEY = "rays-studio:agent-explorer-width";
export const LAST_AGENT_SESSION_KEY = "rays-studio:last-agent-session-id";
export const ONBOARDING_SESSION_KEY = "rays-studio:onboarding-complete";

const LEGACY_KEYS = [
  "rays-user",
  "rays-recent-workspaces",
  "rays-provider-settings",
  "rays-onboarding-complete",
  "rays-agent-sidebar-width",
  "rays-agent-explorer-width",
  "rays-studio:first-run",
] as const;

function isRaysStorageKey(key: string): boolean {
  return (
    key.startsWith("rays-studio:") ||
    key.startsWith("rays-") ||
    key === "rays-user"
  );
}

/** Wipe all RAYS Studio client state (chats, sessions, name, workspaces, UI prefs). */
export function clearAllAppStorage(): void {
  try {
    for (const key of Object.keys(localStorage)) {
      if (isRaysStorageKey(key)) {
        localStorage.removeItem(key);
      }
    }
    for (const key of LEGACY_KEYS) {
      localStorage.removeItem(key);
    }
    sessionStorage.removeItem(ONBOARDING_SESSION_KEY);
    sessionStorage.removeItem("rays-onboarding-complete");
  } catch {
    // ignore private browsing / quota errors
  }
}

/**
 * When the packaged app build id changes (reinstall / new DMG), reset client state.
 * Returns true if storage was cleared.
 */
export function syncInstallEpoch(installEpoch: string): boolean {
  const epoch = String(installEpoch || "dev").trim() || "dev";
  const stored = localStorage.getItem(INSTALL_EPOCH_KEY);
  if (stored === epoch) {
    return false;
  }
  clearAllAppStorage();
  localStorage.setItem(INSTALL_EPOCH_KEY, epoch);
  return true;
}
