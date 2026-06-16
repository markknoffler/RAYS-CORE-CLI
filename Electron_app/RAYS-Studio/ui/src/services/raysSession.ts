import { hostReadFile, hostSelectFolder, hostStartSession, hostStopSession } from "./platformHost";
import { loadAgentChatTurns, saveAgentChatTurns } from "./agentChatStorage";
import { ensureAgentSession, bumpAgentSession, setAgentSessionTitle } from "./agentSessionStorage";
import {
  conversationIdForWorkspace,
  loadProviderSettings,
  rememberWorkspace,
  saveProviderSettings,
  type StoredProviderSettings,
} from "./workspaceStorage";
import {
  createTurn,
  summarizeAction,
  summarizeToolResult,
  type ActivityItem,
  type AgentTurn,
} from "./agentActivity";

export type FileNode = { name: string; type: "file" | "folder"; children?: FileNode[] };
export type DiffLine = { content: string; type: "add" | "remove" };
export type DiffChunk = {
  id: string;
  filePath: string;
  reason?: string;
  added: number;
  removed: number;
  lines: DiffLine[];
};
export type ChatMessage = {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
  title?: string;
  kind?: "default" | "orchestration";
};
export type TerminalLine = { id: string; kind: "output" | "command"; content: string };
export type ProviderConfig = {
  provider: "ollama" | "gemini" | "openai";
  model: string;
  apiKey?: string;
};
export type PromptMode = "agent" | "code" | "chat";
export type ApprovalRequest = { id: string; message: string };
export type ThinkingPhase = "hidden" | "active" | "streaming" | "done";

export type SessionState = {
  sessionId: string | null;
  wsPort: number | null;
  connected: boolean;
  status: "idle" | "running" | "ready" | "disconnected" | "starting";
  workspaceRoot: string | null;
  conversationId: string | null;
  fileTree: FileNode[];
  diffChunks: DiffChunk[];
  chatMessages: ChatMessage[];
  terminalLines: TerminalLine[];
  error: string | null;
  fileContents: Record<string, string>;
  hudPhase: string;
  hudDetail: string;
  tokenCount: number;
  pendingApproval: ApprovalRequest | null;
  executionMode: "ask" | "autonomous";
  thinkingPhase: ThinkingPhase;
  thinkingText: string;
  turns: AgentTurn[];
};

type Subscriber = (state: SessionState) => void;

const initialState: SessionState = {
  sessionId: null,
  wsPort: null,
  connected: false,
  status: "disconnected",
  workspaceRoot: null,
  conversationId: null,
  fileTree: [],
  diffChunks: [],
  chatMessages: [],
  terminalLines: [],
  error: null,
  fileContents: {},
  hudPhase: "",
  hudDetail: "",
  tokenCount: 0,
  pendingApproval: null,
  executionMode: "autonomous",
  thinkingPhase: "hidden",
  thinkingText: "",
  turns: [],
};

class RAYSSessionStore {
  private state: SessionState = initialState;
  private ws: WebSocket | null = null;
  private subscribers = new Set<Subscriber>();
  private wsGeneration = 0;
  private switchToken = 0;

  subscribe(subscriber: Subscriber): () => void {
    this.subscribers.add(subscriber);
    subscriber(this.state);
    return () => {
      this.subscribers.delete(subscriber);
    };
  }

  private publish() {
    for (const subscriber of this.subscribers) {
      subscriber(this.state);
    }
  }

  private setState(next: Partial<SessionState>) {
    this.state = { ...this.state, ...next };
    if (next.turns !== undefined && this.state.conversationId) {
      saveAgentChatTurns(this.state.conversationId, this.state.turns);
    }
    this.publish();
  }

  private appendChatMessage(payload: {
    role?: string;
    content?: string;
    title?: string;
    kind?: ChatMessage["kind"];
  }) {
    const message: ChatMessage = {
      id: crypto.randomUUID(),
      role: payload.role === "user" ? "user" : payload.role === "system" ? "system" : "agent",
      content: payload.content || "",
      title: payload.title,
      kind: payload.kind || "default",
    };
    this.setState({ chatMessages: [...this.state.chatMessages, message] });
  }

  private patchActiveTurn(patch: (turn: AgentTurn) => AgentTurn) {
    const turns = this.state.turns;
    if (turns.length === 0) return;
    const idx = turns.length - 1;
    if (turns[idx].status !== "running") return;
    const next = [...turns];
    next[idx] = patch(turns[idx]);
    this.setState({ turns: next });
  }

  private appendActivityItem(item: ActivityItem) {
    this.patchActiveTurn((turn) => ({
      ...turn,
      items: [...turn.items, item],
    }));
  }

  private upsertThinking(thought: string) {
    this.patchActiveTurn((turn) => {
      const items = [...turn.items];
      const idx = items.findIndex((i) => i.kind === "thinking" && i.status === "running");
      if (idx >= 0) {
        const existing = items[idx] as Extract<ActivityItem, { kind: "thinking" }>;
        const nextText = existing.text ? `${existing.text}\n\n${thought}` : thought;
        items[idx] = { ...existing, text: nextText };
      } else {
        items.push({
          kind: "thinking",
          id: crypto.randomUUID(),
          text: thought,
          status: "running",
          startedAt: Date.now(),
        });
      }
      return { ...turn, items };
    });
  }

  private finalizeRunningThinking() {
    this.patchActiveTurn((turn) => ({
      ...turn,
      items: turn.items.map((item) => {
        if (item.kind === "thinking" && item.status === "running") {
          return {
            ...item,
            status: "done" as const,
            durationMs: Date.now() - item.startedAt,
          };
        }
        return item;
      }),
    }));
  }

  private completeActiveTurn(finalSummary?: string) {
    const turns = this.state.turns;
    if (turns.length === 0) return;
    const idx = turns.length - 1;
    const turn = turns[idx];
    const next = [...turns];
    next[idx] = {
      ...turn,
      status: "done",
      endedAt: turn.endedAt || Date.now(),
      finalSummary: finalSummary || turn.finalSummary,
      items: turn.items.map((item) => {
        if (item.kind === "thinking" && item.status === "running") {
          return {
            ...item,
            status: "done" as const,
            durationMs: Date.now() - item.startedAt,
          };
        }
        if (item.kind === "tool" && item.status === "running") {
          return {
            ...item,
            status: "done" as const,
            durationMs: Date.now() - item.startedAt,
          };
        }
        if (item.kind === "command" && item.status === "running") {
          return {
            ...item,
            status: "done" as const,
            durationMs: Date.now() - item.startedAt,
          };
        }
        if (item.kind === "action" && item.status === "running") {
          return {
            ...item,
            status: "done" as const,
            durationMs: Date.now() - item.startedAt,
          };
        }
        return item;
      }),
    };
    this.setState({ turns: next });
  }

  private saveCurrentChat() {
    const { conversationId, turns } = this.state;
    if (conversationId && turns.length > 0) {
      saveAgentChatTurns(conversationId, turns);
    }
  }

  async startSession(
    workspacePath: string,
    providerConfig?: ProviderConfig,
    conversationId?: string
  ): Promise<void> {
    await this.switchSession(workspacePath, conversationId, providerConfig);
  }

  async switchSession(
    workspacePath: string,
    conversationId?: string,
    providerConfig?: ProviderConfig
  ): Promise<void> {
    const switchId = ++this.switchToken;
    this.saveCurrentChat();

    if (this.state.status === "running" && this.ws?.readyState === WebSocket.OPEN) {
      this.sendCommand("cancel_current_task");
    }

    this.wsGeneration += 1;
    this.ws?.close();
    this.ws = null;

    const previousSessionId = this.state.sessionId;
    if (previousSessionId) {
      await hostStopSession(previousSessionId);
    }

    if (switchId !== this.switchToken) return;

    const settings: StoredProviderSettings = providerConfig ?? loadProviderSettings();
    saveProviderSettings(settings);
    rememberWorkspace(workspacePath);
    const resolvedConversationId = conversationId || conversationIdForWorkspace(workspacePath);
    ensureAgentSession(workspacePath, resolvedConversationId);
    const restoredTurns = loadAgentChatTurns(resolvedConversationId);

    this.setState({
      sessionId: null,
      wsPort: null,
      connected: false,
      status: "starting",
      workspaceRoot: workspacePath,
      conversationId: resolvedConversationId,
      turns: restoredTurns,
      fileTree: [],
      diffChunks: [],
      chatMessages: [],
      terminalLines: [],
      error: null,
      fileContents: {},
      hudPhase: "",
      hudDetail: "",
      tokenCount: 0,
      pendingApproval: null,
      thinkingPhase: "hidden",
      thinkingText: "",
    });

    const { sessionId, wsPort } = await hostStartSession(
      workspacePath,
      settings,
      resolvedConversationId
    );

    if (switchId !== this.switchToken) {
      await hostStopSession(sessionId);
      return;
    }

    this.setState({
      sessionId,
      wsPort,
      status: "ready",
      workspaceRoot: workspacePath,
      conversationId: resolvedConversationId,
      turns: restoredTurns,
    });
    this.connectSocket(wsPort);
  }

  async stopSession(): Promise<void> {
    this.saveCurrentChat();
    this.switchToken += 1;
    this.wsGeneration += 1;
    this.ws?.close();
    this.ws = null;
    if (this.state.sessionId) {
      await hostStopSession(this.state.sessionId);
    }
    this.setState(initialState);
  }

  private connectSocket(port: number) {
    const gen = ++this.wsGeneration;
    this.ws?.close();
    const ws = new WebSocket(`ws://127.0.0.1:${port}`);
    this.ws = ws;
    ws.onopen = () => {
      if (gen !== this.wsGeneration) return;
      this.setState({ connected: true });
      this.sendCommand("ping");
      this.sendCommand("refresh_tree");
    };
    ws.onclose = () => {
      if (gen !== this.wsGeneration) return;
      this.setState({ connected: false, status: "disconnected" });
    };
    ws.onerror = () => {
      if (gen !== this.wsGeneration) return;
      this.setState({ error: "WebSocket connection failed" });
    };
    ws.onmessage = (event) => {
      if (gen !== this.wsGeneration) return;
      const envelope = JSON.parse(event.data);
      const eventType = envelope.type;
      const payload = envelope.payload || {};

      if (eventType === "session_status") {
        const nextStatus = payload.status as SessionState["status"] | undefined;
        const wasRunning = this.state.status === "running";
        const updates: Partial<SessionState> = {
          status: nextStatus || this.state.status,
          workspaceRoot: payload.workspaceRoot || this.state.workspaceRoot,
        };
        if (nextStatus === "running") {
          updates.thinkingPhase = "active";
        } else if (wasRunning && nextStatus === "idle") {
          updates.thinkingPhase = "streaming";
          this.finalizeRunningThinking();
          this.completeActiveTurn();
        }
        this.setState(updates);
        return;
      }

      if (eventType === "file_tree_snapshot") {
        this.setState({
          fileTree: payload.nodes || this.state.fileTree,
          workspaceRoot: payload.rootPath || this.state.workspaceRoot,
        });
        return;
      }

      if (eventType === "chat_history_snapshot") {
        const items = (payload.messages || []) as Array<{
          role?: string;
          content?: string;
          title?: string;
        }>;
        const messages: ChatMessage[] = items.map((item) => ({
          id: crypto.randomUUID(),
          role: (item.role === "user" ? "user" : "agent") as ChatMessage["role"],
          content: item.content || "",
          title: item.title,
        }));
        this.setState({ chatMessages: messages });
        return;
      }

      if (eventType === "chat_message") {
        if (payload.role === "user") {
          const last = this.state.chatMessages[this.state.chatMessages.length - 1];
          if (last?.role === "user" && last.content === (payload.content || "")) {
            return;
          }
        }
        const title = String(payload.title || "");
        const content = String(payload.content || "");
        if (title === "Final Run Summary" || title === "Session Summary") {
          this.completeActiveTurn(content);
          this.appendChatMessage({ role: "agent", title, content, kind: "default" });
          return;
        }
        if (payload.kind === "orchestration" || title.startsWith("Tool ·")) {
          return;
        }
        if (payload.role === "agent" && content) {
          this.completeActiveTurn(content);
        }
        this.appendChatMessage(payload);
        return;
      }

      if (eventType === "approval_request") {
        const message = String(payload.message || "Approve this action?");
        this.appendActivityItem({
          kind: "question",
          id: String(payload.id || crypto.randomUUID()),
          question: message,
          status: "pending",
        });
        this.setState({
          pendingApproval: {
            id: String(payload.id || ""),
            message,
          },
        });
        return;
      }

      if (eventType === "execution_mode") {
        const mode = payload.mode === "ask" ? "ask" : "autonomous";
        this.setState({ executionMode: mode });
        return;
      }

      if (eventType === "hud_status") {
        this.setState({
          hudPhase: String(payload.phase || ""),
          hudDetail: String(payload.detail || ""),
        });
        return;
      }

      if (eventType === "hud_tokens") {
        const count = Number(payload.count || 0);
        if (count > 0) {
          this.setState({ tokenCount: this.state.tokenCount + count });
        }
        return;
      }

      if (eventType === "hud_note") {
        const level =
          payload.level === "warn"
            ? "warn"
            : payload.level === "error"
              ? "error"
              : "info";
        this.appendActivityItem({
          kind: "note",
          id: crypto.randomUUID(),
          level,
          message: String(payload.message || ""),
        });
        return;
      }

      if (eventType.startsWith("orchestration_")) {
        this.handleOrchestrationEvent(eventType, payload);
        return;
      }

      if (eventType === "mcp_status") {
        this.appendChatMessage({
          role: "agent",
          title: "MCP Status",
          content: String(payload.content || ""),
        });
        return;
      }

      if (eventType === "diff_chunk") {
        const chunk: DiffChunk = {
          id: crypto.randomUUID(),
          filePath: payload.filePath || "",
          reason: payload.reason,
          added: payload.added || 0,
          removed: payload.removed || 0,
          lines: payload.lines || [],
        };
        this.setState({ diffChunks: [...this.state.diffChunks, chunk] });
        return;
      }

      if (eventType === "command_finished") {
        const command = String(payload.command || "");
        const output = String(payload.output || "");
        const elapsed = Number(payload.elapsed || 0);
        this.patchActiveTurn((turn) => {
          const items = [...turn.items];
          const idx = items.findIndex(
            (i) => i.kind === "command" && i.command === command && i.status === "running"
          );
          if (idx >= 0) {
            const existing = items[idx] as Extract<ActivityItem, { kind: "command" }>;
            items[idx] = {
              ...existing,
              status: "done",
              durationMs: elapsed > 0 ? elapsed * 1000 : Date.now() - existing.startedAt,
              output: output.slice(-2000),
            };
          } else {
            items.push({
              kind: "command",
              id: crypto.randomUUID(),
              command,
              status: "done",
              startedAt: Date.now(),
              durationMs: elapsed > 0 ? elapsed * 1000 : undefined,
              output: output.slice(-2000),
            });
          }
          return { ...turn, items };
        });
        const lines = output
          .split("\n")
          .filter((line) => line.trim())
          .slice(-20)
          .map((line) => ({ id: crypto.randomUUID(), kind: "output" as const, content: line }));
        this.setState({
          terminalLines: [...this.state.terminalLines, ...lines],
        });
        return;
      }
      if (eventType === "command_started") {
        const command = String(payload.command || "");
        this.appendActivityItem({
          kind: "command",
          id: crypto.randomUUID(),
          command,
          status: "running",
          startedAt: Date.now(),
        });
        this.setState({
          terminalLines: [
            ...this.state.terminalLines,
            { id: crypto.randomUUID(), kind: "command", content: `$ ${command}` },
          ],
        });
        return;
      }

      if (eventType === "terminal_output") {
        this.setState({
          terminalLines: [
            ...this.state.terminalLines,
            { id: crypto.randomUUID(), kind: "output", content: payload.line || "" },
          ].slice(-500),
        });
        return;
      }

      if (eventType === "error") {
        const message = String(payload.message || "Unknown error");
        this.setState({ error: message });
        this.appendChatMessage({
          role: "system",
          title: payload.level === "fatal" ? "Backend error" : "Notice",
          content: message,
        });
      }
    };
  }

  private handleOrchestrationEvent(eventType: string, payload: Record<string, unknown>) {
    if (eventType === "orchestration_session") {
      this.setState({
        tokenCount: 0,
        hudPhase: "Planning",
        hudDetail: "",
        thinkingPhase: "active",
        thinkingText: "",
      });
      this.upsertThinking("");
      return;
    }
    if (eventType === "orchestration_thinking") {
      const thought = String(payload.thought || "").trim();
      if (!thought) return;
      const nextText = this.state.thinkingText
        ? `${this.state.thinkingText}\n\n${thought}`
        : thought;
      this.setState({
        thinkingText: nextText,
        thinkingPhase: this.state.thinkingPhase === "hidden" ? "active" : this.state.thinkingPhase,
      });
      this.upsertThinking(thought);
      return;
    }
    if (eventType === "orchestration_step") {
      this.finalizeRunningThinking();
      const label = String(payload.label || payload.title || "Step");
      const spawnReason = String(payload.spawnReason || "");
      if (label.startsWith("mcp/")) {
        const server = label.replace(/^mcp\//, "");
        this.appendActivityItem({
          kind: "tool",
          id: crypto.randomUUID(),
          server,
          tool: "…",
          title: `Running · ${server}`,
          summary: spawnReason || "Running MCP tool",
          detail: "",
          status: "running",
          startedAt: Date.now(),
        });
      } else {
        this.appendActivityItem({
          kind: "action",
          id: crypto.randomUUID(),
          verb: label.startsWith("skill/") ? `Running ${label}` : label,
          detail: spawnReason,
          ok: true,
          status: "running",
          startedAt: Date.now(),
        });
      }
      return;
    }
    if (eventType === "orchestration_action") {
      const verb = String(payload.verb || "Action");
      if (["Listed", "Ran", "Read", "Wrote", "Edited", "Called"].includes(verb)) {
        return;
      }
      const detail = String(payload.detail || "");
      const ok = payload.ok !== false;
      this.appendActivityItem({
        kind: "action",
        id: crypto.randomUUID(),
        verb,
        detail: summarizeAction(verb, detail, ok),
        ok,
        status: ok ? "done" : "error",
        startedAt: Date.now(),
        durationMs: 0,
      });
      return;
    }
    if (eventType === "orchestration_plan") {
      const plan = (payload.plan || []) as Array<Record<string, unknown>>;
      if (plan.length === 0) return;
      this.appendActivityItem({
        kind: "action",
        id: crypto.randomUUID(),
        verb: "Planned steps",
        detail: `${plan.length} step${plan.length === 1 ? "" : "s"}`,
        ok: true,
        status: "done",
        startedAt: Date.now(),
        durationMs: 0,
      });
      return;
    }
    if (eventType === "orchestration_capabilities") {
      return;
    }
    if (eventType === "orchestration_tool_result") {
      const server = String(payload.server || "");
      const tool = String(payload.tool || "");
      const result = String(payload.result || "");
      const { title, summary, detail } = summarizeToolResult(server, tool, result);
      const startedAt = Date.now();

      this.patchActiveTurn((turn) => {
        const items = [...turn.items];
        const runningIdx = items.findIndex(
          (i) =>
            i.kind === "tool" &&
            i.status === "running" &&
            (i.server === server || i.title.includes(server))
        );
        if (runningIdx >= 0) {
          const existing = items[runningIdx] as Extract<ActivityItem, { kind: "tool" }>;
          items[runningIdx] = {
            ...existing,
            tool,
            title,
            summary,
            detail,
            status: "done",
            durationMs: Date.now() - existing.startedAt,
          };
        } else {
          items.push({
            kind: "tool",
            id: crypto.randomUUID(),
            server,
            tool,
            title,
            summary,
            detail,
            status: "done",
            startedAt,
            durationMs: 0,
          });
        }
        return { ...turn, items };
      });
      return;
    }
    if (eventType === "orchestration_validation") {
      const complete = Boolean(payload.complete);
      const reasoning = String(payload.reasoning || "");
      this.appendActivityItem({
        kind: "action",
        id: crypto.randomUUID(),
        verb: complete ? "Validated" : "Needs follow-up",
        detail: reasoning,
        ok: complete,
        status: "done",
        startedAt: Date.now(),
        durationMs: 0,
      });
      return;
    }
    if (eventType === "orchestration_summary") {
      const result = (payload.result || {}) as Record<string, unknown>;
      const narrative = String(result.narrative_summary || result.summary || "");
      const chatTitle = String(result.chat_title || "").trim();
      if (chatTitle && this.state.conversationId) {
        setAgentSessionTitle(this.state.conversationId, chatTitle);
      }
      this.completeActiveTurn(narrative || "Orchestration complete.");
      return;
    }
    if (eventType === "orchestration_section") {
      return;
    }
  }

  submitPrompt(prompt: string, mode: PromptMode = "agent") {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    const last = this.state.chatMessages[this.state.chatMessages.length - 1];
    if (!(last?.role === "user" && last.content === trimmed)) {
      this.appendChatMessage({ role: "user", content: trimmed });
    }
    const turn = createTurn(trimmed);
    if (this.state.conversationId) {
      bumpAgentSession(this.state.conversationId);
    }
    this.setState({
      turns: [...this.state.turns, turn],
      thinkingPhase: "active",
      thinkingText: "",
    });
    this.sendCommand("submit_prompt", { prompt: trimmed, mode });
  }

  completeThinkingReveal() {
    if (this.state.thinkingPhase === "streaming") {
      this.setState({ thinkingPhase: "done" });
    }
  }

  respondApproval(approved: boolean) {
    const pending = this.state.pendingApproval;
    if (!pending) return;
    this.sendCommand("approval_response", { id: pending.id, approved });
    this.setState({ pendingApproval: null });
  }

  setExecutionMode(mode: "ask" | "autonomous") {
    this.sendCommand("set_execution_mode", { mode });
    this.setState({ executionMode: mode });
  }

  listMcpStatus() {
    this.sendCommand("list_mcp");
  }

  reloadMcp() {
    this.sendCommand("reload_mcp");
  }

  refreshTree() {
    this.sendCommand("refresh_tree");
  }

  sendTerminalInput(input: string) {
    this.sendCommand("terminal_input", { input });
  }

  cancelCurrentTask() {
    this.sendCommand("cancel_current_task");
  }

  async selectFolder(): Promise<string> {
    return hostSelectFolder();
  }

  async readFile(relativePath: string): Promise<string> {
    if (this.state.fileContents[relativePath] !== undefined) {
      return this.state.fileContents[relativePath];
    }
    if (!this.state.workspaceRoot) {
      throw new Error("No workspace selected");
    }
    const content = await hostReadFile(this.state.workspaceRoot, relativePath);
    this.setState({
      fileContents: {
        ...this.state.fileContents,
        [relativePath]: content,
      },
    });
    return content;
  }

  private sendCommand(command: string, payload: Record<string, unknown> = {}) {
    const ws = this.ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ command, payload }));
  }
}

export const raysSessionStore = new RAYSSessionStore();
