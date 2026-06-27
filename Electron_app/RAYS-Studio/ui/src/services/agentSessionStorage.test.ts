import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createAgentSession,
  listAgentSessions,
  removeAgentSession,
  renameAgentSession,
  sessionsByWorkspace,
  workspaceLabel,
} from "./agentSessionStorage";

describe("agentSessionStorage", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("crypto", {
      randomUUID: () => "test-session-id",
    });
  });

  it("creates and lists sessions newest first", () => {
    createAgentSession("/tmp/ws", "First");
    createAgentSession("/tmp/ws", "Second");
    const titles = listAgentSessions().map((s) => s.title);
    expect(titles).toEqual(["Second", "First"]);
  });

  it("groups sessions by workspace path", () => {
    createAgentSession("/tmp/a", "A");
    createAgentSession("/tmp/b", "B");
    const grouped = sessionsByWorkspace();
    expect(Object.keys(grouped).sort()).toEqual(["/tmp/a", "/tmp/b"]);
  });

  it("renames and removes sessions", () => {
    const session = createAgentSession("/tmp/ws", "Old");
    renameAgentSession(session.id, "New title");
    expect(listAgentSessions()[0]?.title).toBe("New title");
    removeAgentSession(session.id);
    expect(listAgentSessions()).toHaveLength(0);
  });

  it("workspaceLabel uses the final path segment", () => {
    expect(workspaceLabel("/home/user/my-repo")).toBe("my-repo");
    expect(workspaceLabel("C:\\Users\\dev\\project")).toBe("project");
  });
});
