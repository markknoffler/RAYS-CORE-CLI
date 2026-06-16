#!/usr/bin/env python3
"""
WebSocket bridge that adapts RAYS CLI output to GUI events.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from rays_core.config_locator import resolve_config_path

try:
    from websockets.asyncio.server import serve
except ImportError:  # pragma: no cover - older websockets
    try:
        from websockets.server import serve  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: websockets. Install with `pip install rays-gui-bridge`."
        ) from exc

ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text or "")


class ApprovalManager:
    """GUI approval requests block worker threads until the UI responds."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._pending: Dict[str, threading.Event] = {}
        self._results: Dict[str, bool] = {}
        self._lock = threading.Lock()

    def request(self, message: str, timeout: float = 300.0) -> bool:
        approval_id = uuid.uuid4().hex
        event = threading.Event()
        with self._lock:
            self._pending[approval_id] = event
        self.bus.emit("approval_request", {"id": approval_id, "message": message})
        if not event.wait(timeout):
            with self._lock:
                self._pending.pop(approval_id, None)
                self._results.pop(approval_id, None)
            return False
        with self._lock:
            approved = self._results.pop(approval_id, False)
            self._pending.pop(approval_id, None)
        return approved

    def respond(self, approval_id: str, approved: bool) -> None:
        with self._lock:
            event = self._pending.get(approval_id)
            if event is None:
                return
            self._results[approval_id] = approved
            event.set()


class EventBus:
    def __init__(self) -> None:
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.clients: set[Any] = set()
        self.session_id = f"session-{int(time.time())}"
        self._lock = threading.Lock()

    async def broadcast(self, event: Dict[str, Any]) -> None:
        if not self.clients:
            return
        payload = json.dumps(event)
        dead_clients = []
        for client in list(self.clients):
            try:
                await client.send(payload)
            except Exception:
                dead_clients.append(client)
        for client in dead_clients:
            self.clients.discard(client)

    def emit(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
        if self.loop is None:
            return
        body = {
            "type": event_type,
            "sessionId": self.session_id,
            "timestamp": time.time(),
            "payload": payload or {},
        }
        asyncio.run_coroutine_threadsafe(self.broadcast(body), self.loop)

    def snapshot_tree(self, workspace_root: Path) -> List[Dict[str, Any]]:
        def walk(path: Path) -> List[Dict[str, Any]]:
            nodes: List[Dict[str, Any]] = []
            try:
                children = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            except Exception:
                return nodes
            for child in children:
                if child.name in {".git", ".rays", "node_modules", "__pycache__"}:
                    continue
                if child.is_dir():
                    nodes.append(
                        {"name": child.name, "type": "folder", "children": walk(child)}
                    )
                else:
                    nodes.append({"name": child.name, "type": "file"})
            return nodes

        return walk(workspace_root)


class GUIBridgeRuntime:
    def __init__(
        self,
        workspace_root: Path,
        config_path: str,
        bus: EventBus,
        runtime_overrides: Optional[Dict[str, Any]] = None,
    ):
        self.workspace_root = workspace_root
        self.config_path = config_path
        self.bus = bus
        self.runtime_overrides = runtime_overrides or {}
        self.rays: Optional[Any] = None
        self._busy = False
        self._patch_applied = False
        self.approval_manager = ApprovalManager(bus=self.bus)
        self.shell = PersistentShell(workspace_root=self.workspace_root, bus=self.bus)
        self._ready = False

    def initialize(self, conversation_id: Optional[str] = None) -> None:
        from rays_core.rays_main import RAYS

        self.rays = RAYS(
            codebase_root=str(self.workspace_root),
            config_path=self.config_path,
            conversation_id=conversation_id,
            runtime_overrides=self.runtime_overrides,
        )
        # GUI sessions must be non-interactive to avoid blocking on stdin prompts.
        self.rays.set_execution_mode("autonomous")
        self._patch_ui_events()
        try:
            sessions = self.rays.mcp_manager.connect_all()
            connected = [
                name
                for name, sess in sessions.items()
                if sess.status == "connected"
            ]
            if connected:
                self.bus.emit(
                    "hud_note",
                    {
                        "level": "info",
                        "message": f"MCP connected: {', '.join(connected)}",
                    },
                )
            else:
                self.bus.emit(
                    "hud_note",
                    {
                        "level": "warn",
                        "message": "No MCP servers connected. Check ~/.rays/mcp.json and Blender addon (port 9876).",
                    },
                )
        except Exception as exc:
            self.bus.emit(
                "hud_note",
                {"level": "warn", "message": f"MCP preload failed: {exc}"},
            )
        self.bus.emit(
            "session_status",
            {"status": "ready", "workspaceRoot": str(self.workspace_root)},
        )
        self.bus.emit(
            "file_tree_snapshot",
            {"rootPath": str(self.workspace_root), "nodes": self.bus.snapshot_tree(self.workspace_root)},
        )
        self.shell.start()
        self._ready = True

    def emit_restored_chat_history(self) -> None:
        if self.rays is None:
            return
        try:
            memories = self.rays.memory_mgr.retrieve_last_n_memories(12)
        except Exception:
            memories = []
        messages: List[Dict[str, Any]] = []
        for item in memories:
            summary = (item.get("summary") or "").strip()
            if not summary:
                continue
            name = item.get("name") or "Previous session"
            messages.append(
                {
                    "role": "agent",
                    "title": str(name),
                    "content": summary,
                }
            )
        if messages:
            self.bus.emit("chat_history_snapshot", {"messages": messages})

    def _patch_ui_events(self) -> None:
        if self._patch_applied:
            return
        self._patch_applied = True

        from rays_core import rays_ui

        original_print_diff = rays_ui.print_diff
        original_print_command_box = rays_ui.print_command_box
        original_print_file_tree = rays_ui.print_file_tree
        original_print_full_width_box = rays_ui.print_full_width_box
        original_capture_print = rays_ui.capture_print
        original_print_warning = rays_ui.print_warning
        original_print_error = rays_ui.print_error
        original_print_file_created = rays_ui.print_file_created
        original_print_final_run_summary = rays_ui.print_final_run_summary

        def wrapped_print_diff(file_path: str, search_block: str, replace_block: str, reason: str = ""):
            lines = []
            for line in replace_block.splitlines()[:80]:
                lines.append({"content": line, "type": "add"})
            for line in search_block.splitlines()[:80]:
                lines.append({"content": line, "type": "remove"})
            self.bus.emit(
                "diff_chunk",
                {
                    "filePath": file_path,
                    "reason": reason,
                    "added": len(replace_block.splitlines()),
                    "removed": len(search_block.splitlines()),
                    "lines": lines,
                },
            )
            return original_print_diff(file_path, search_block, replace_block, reason)

        def wrapped_print_command_box(command: str, output: str = "", elapsed: float = 0, success: bool = True):
            self.bus.emit(
                "command_finished",
                {
                    "command": command,
                    "elapsed": elapsed,
                    "success": success,
                    "output": strip_ansi(output),
                },
            )
            return original_print_command_box(command, output, elapsed, success)

        def wrapped_print_file_tree(files: List[str], selected: Optional[List[str]] = None, title: str = ""):
            self.bus.emit(
                "file_tree_snapshot",
                {
                    "rootPath": str(self.workspace_root),
                    "title": title or "Workspace files",
                    "files": files,
                    "selected": selected or [],
                    "nodes": self.bus.snapshot_tree(self.workspace_root),
                },
            )
            return original_print_file_tree(files, selected, title)

        def wrapped_print_full_width_box(title: str, content: str, color: str = "", content_color: str = ""):
            if (title or "").strip().lower() == "final run summary":
                return original_print_full_width_box(title, content, color, content_color)
            self.bus.emit(
                "chat_message",
                {
                    "role": "agent",
                    "title": title,
                    "content": strip_ansi(content),
                },
            )
            return original_print_full_width_box(title, content, color, content_color)

        def wrapped_capture_print(message: str, *, force: bool = False):
            clean = strip_ansi(message).rstrip()
            if clean:
                self.bus.emit("terminal_output", {"line": clean})
            return original_capture_print(message, force=force)

        def wrapped_print_warning(message: str):
            self.bus.emit("error", {"level": "warning", "message": strip_ansi(message)})
            return original_print_warning(message)

        def wrapped_print_error(message: str):
            self.bus.emit("error", {"level": "error", "message": strip_ansi(message)})
            return original_print_error(message)

        def wrapped_print_file_created(file_path: str, content: str):
            self.bus.emit(
                "diff_chunk",
                {
                    "filePath": file_path,
                    "reason": "Created file",
                    "added": len(content.splitlines()),
                    "removed": 0,
                    "lines": [{"content": line, "type": "add"} for line in content.splitlines()[:120]],
                },
            )
            return original_print_file_created(file_path, content)

        def wrapped_print_final_run_summary(summary_text: str):
            self.bus.emit(
                "chat_message",
                {
                    "role": "agent",
                    "title": "Final Run Summary",
                    "content": strip_ansi(summary_text or ""),
                },
            )
            return original_print_final_run_summary(summary_text)

        rays_ui.print_diff = wrapped_print_diff
        rays_ui.print_command_box = wrapped_print_command_box
        rays_ui.print_file_tree = wrapped_print_file_tree
        rays_ui.print_full_width_box = wrapped_print_full_width_box
        rays_ui.capture_print = wrapped_capture_print
        rays_ui.print_warning = wrapped_print_warning
        rays_ui.print_error = wrapped_print_error
        rays_ui.print_file_created = wrapped_print_file_created
        rays_ui.print_final_run_summary = wrapped_print_final_run_summary

        original_ask_approval = rays_ui.ask_approval
        original_orch_begin_session = rays_ui.orch_begin_session
        original_orch_emit_section = rays_ui.orch_emit_section
        original_orch_emit_thinking = rays_ui.orch_emit_thinking
        original_orch_emit_action = rays_ui.orch_emit_action
        original_orch_emit_plan = rays_ui.orch_emit_plan
        original_orch_emit_capabilities = rays_ui.orch_emit_capabilities
        original_orch_emit_step_header = rays_ui.orch_emit_step_header
        original_orch_emit_tool_result = rays_ui.orch_emit_tool_result
        original_orch_emit_validation = rays_ui.orch_emit_validation
        original_orch_render_final_summary = rays_ui.orch_render_final_summary
        original_hud_set_status = rays_ui.hud_set_status
        original_hud_add_tokens = rays_ui.hud_add_tokens
        original_hud_note_ok = rays_ui.hud_note_ok
        original_hud_note_warn = rays_ui.hud_note_warn

        def wrapped_ask_approval(message: str) -> bool:
            if self.rays and getattr(self.rays, "execution_mode", "autonomous") == "autonomous":
                return True
            return self.approval_manager.request(message)

        def wrapped_orch_begin_session(user_prompt: str) -> None:
            self.bus.emit("orchestration_session", {"prompt": user_prompt})
            return original_orch_begin_session(user_prompt)

        def wrapped_orch_emit_section(title: str) -> None:
            self.bus.emit("orchestration_section", {"title": title})
            return original_orch_emit_section(title)

        def wrapped_orch_emit_thinking(thought: str) -> None:
            if thought and thought.strip():
                self.bus.emit("orchestration_thinking", {"thought": thought.strip()})
            return original_orch_emit_thinking(thought)

        def wrapped_orch_emit_action(verb: str, detail: str, *, ok: bool = True) -> None:
            self.bus.emit(
                "orchestration_action",
                {"verb": verb, "detail": detail, "ok": ok},
            )
            return original_orch_emit_action(verb, detail, ok=ok)

        def wrapped_orch_emit_plan(summary: str, plan: List[Dict[str, Any]]) -> None:
            self.bus.emit(
                "orchestration_plan",
                {"summary": summary, "plan": plan},
            )
            return original_orch_emit_plan(summary, plan)

        def wrapped_orch_emit_capabilities(
            skills: List[str], mcp_servers: List[str], reasoning: str = ""
        ) -> None:
            self.bus.emit(
                "orchestration_capabilities",
                {"skills": skills, "mcpServers": mcp_servers, "reasoning": reasoning},
            )
            return original_orch_emit_capabilities(skills, mcp_servers, reasoning)

        def wrapped_orch_emit_step_header(label: str, spawn_reason: str = "") -> None:
            self.bus.emit(
                "orchestration_step",
                {"label": label, "spawnReason": spawn_reason},
            )
            return original_orch_emit_step_header(label, spawn_reason)

        def wrapped_orch_emit_tool_result(
            tool: str,
            arguments: Any,
            result: str,
            *,
            server: str = "",
        ) -> None:
            self.bus.emit(
                "orchestration_tool_result",
                {
                    "tool": tool,
                    "arguments": arguments,
                    "result": strip_ansi(str(result)),
                    "server": server,
                },
            )
            return original_orch_emit_tool_result(
                tool, arguments, result, server=server
            )

        def wrapped_orch_emit_validation(is_complete: bool, reasoning: str) -> None:
            self.bus.emit(
                "orchestration_validation",
                {"complete": is_complete, "reasoning": reasoning},
            )
            return original_orch_emit_validation(is_complete, reasoning)

        def wrapped_orch_render_final_summary(result: Dict[str, Any]) -> None:
            self.bus.emit("orchestration_summary", {"result": result})
            return original_orch_render_final_summary(result)

        def wrapped_hud_set_status(phase: str, detail: str = "") -> None:
            self.bus.emit("hud_status", {"phase": phase, "detail": detail})
            return original_hud_set_status(phase, detail)

        def wrapped_hud_add_tokens(count: int) -> None:
            if count > 0:
                self.bus.emit("hud_tokens", {"count": count})
            return original_hud_add_tokens(count)

        def wrapped_hud_note_ok(message: str) -> None:
            self.bus.emit("hud_note", {"level": "ok", "message": message})
            return original_hud_note_ok(message)

        def wrapped_hud_note_warn(message: str) -> None:
            self.bus.emit("hud_note", {"level": "warn", "message": message})
            return original_hud_note_warn(message)

        rays_ui.ask_approval = wrapped_ask_approval
        rays_ui.orch_begin_session = wrapped_orch_begin_session
        rays_ui.orch_emit_section = wrapped_orch_emit_section
        rays_ui.orch_emit_thinking = wrapped_orch_emit_thinking
        rays_ui.orch_emit_action = wrapped_orch_emit_action
        rays_ui.orch_emit_plan = wrapped_orch_emit_plan
        rays_ui.orch_emit_capabilities = wrapped_orch_emit_capabilities
        rays_ui.orch_emit_step_header = wrapped_orch_emit_step_header
        rays_ui.orch_emit_tool_result = wrapped_orch_emit_tool_result
        rays_ui.orch_emit_validation = wrapped_orch_emit_validation
        rays_ui.orch_render_final_summary = wrapped_orch_render_final_summary
        rays_ui.hud_set_status = wrapped_hud_set_status
        rays_ui.hud_add_tokens = wrapped_hud_add_tokens
        rays_ui.hud_note_ok = wrapped_hud_note_ok
        rays_ui.hud_note_warn = wrapped_hud_note_warn

    def _resolve_prompt_execution(self, prompt: str, mode: str) -> tuple[Optional[str], str]:
        text = (prompt or "").strip()
        if text.startswith("/"):
            parts = text.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""
            if cmd == "/code":
                return arg or None, "code"
            if cmd == "/chat":
                return arg or None, "chat"
            if cmd == "/mcp":
                return None, "mcp"
        normalized = mode if mode in {"agent", "code", "chat"} else "agent"
        if normalized == "run":
            normalized = "code"
        return text or None, normalized

    def run_prompt(self, prompt: str, mode: str = "agent") -> None:
        if not self._ready or self.rays is None:
            self.bus.emit(
                "error",
                {
                    "level": "warning",
                    "message": "RAYS engine is still starting. Wait for Ready status, then try again.",
                },
            )
            return
        if self._busy:
            self.bus.emit("error", {"level": "error", "message": "Session is busy"})
            return

        resolved_prompt, resolved_mode = self._resolve_prompt_execution(prompt, mode)
        if resolved_mode == "mcp":
            def mcp_worker() -> None:
                self._busy = True
                try:
                    self.bus.emit("session_status", {"status": "running"})
                    status = self.rays.agent_orchestrator.list_mcp_status()
                    self.bus.emit(
                        "chat_message",
                        {"role": "agent", "title": "MCP Status", "content": strip_ansi(status)},
                    )
                except Exception as exc:
                    self.bus.emit("error", {"level": "error", "message": str(exc)})
                finally:
                    self.bus.emit("session_status", {"status": "idle"})
                    self._busy = False

            threading.Thread(target=mcp_worker, daemon=True).start()
            return

        if not resolved_prompt:
            self.bus.emit("error", {"level": "warning", "message": "Prompt is empty"})
            return

        def worker() -> None:
            self._busy = True
            try:
                self.bus.emit("session_status", {"status": "running"})
                self.bus.emit("chat_message", {"role": "user", "content": resolved_prompt})
                if resolved_mode == "chat":
                    self.rays.run_chat_mode(resolved_prompt)
                elif resolved_mode == "code":
                    self.rays.run(resolved_prompt)
                else:
                    self.rays.agent_orchestrator.run(user_prompt=resolved_prompt)
                self.bus.emit("session_status", {"status": "idle"})
                self.bus.emit(
                    "file_tree_snapshot",
                    {
                        "rootPath": str(self.workspace_root),
                        "nodes": self.bus.snapshot_tree(self.workspace_root),
                    },
                )
            except Exception as exc:
                self.bus.emit(
                    "error",
                    {
                        "level": "error",
                        "message": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                )
                self.bus.emit("session_status", {"status": "idle"})
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()

    def set_execution_mode(self, mode: str) -> None:
        if self.rays is None:
            return
        normalized = "autonomous" if mode == "autonomous" else "ask"
        self.rays.set_execution_mode(normalized)
        self.bus.emit("execution_mode", {"mode": normalized})

    def list_mcp_status(self) -> None:
        if self.rays is None:
            self.bus.emit("error", {"level": "warning", "message": "RAYS engine is still starting."})
            return

        def worker() -> None:
            try:
                status = self.rays.agent_orchestrator.list_mcp_status()
                self.bus.emit("mcp_status", {"content": strip_ansi(status)})
            except Exception as exc:
                self.bus.emit("error", {"level": "error", "message": str(exc)})

        threading.Thread(target=worker, daemon=True).start()

    def reload_mcp(self) -> None:
        if self.rays is None:
            self.bus.emit("error", {"level": "warning", "message": "RAYS engine is still starting."})
            return

        def worker() -> None:
            try:
                status = self.rays.agent_orchestrator.reload_mcp_servers()
                self.bus.emit(
                    "mcp_status",
                    {"content": strip_ansi(status), "reloaded": True},
                )
            except Exception as exc:
                self.bus.emit("error", {"level": "error", "message": str(exc)})

        threading.Thread(target=worker, daemon=True).start()

    def execute_terminal_input(self, command: str) -> None:
        self.shell.execute(command)

    def shutdown(self) -> None:
        if self.rays is not None:
            try:
                self.rays.mcp_manager.shutdown()
            except Exception:
                pass
        self.shell.stop()


class PersistentShell:
    """
    Keeps a single shell process alive for the whole GUI session.
    Commands execute in-session, so cwd/env state persists naturally.
    """

    MARKER_PREFIX = "__RAYS_CMD_DONE__:"

    def __init__(self, workspace_root: Path, bus: EventBus):
        self.workspace_root = workspace_root
        self.bus = bus
        self.proc: Optional[subprocess.Popen[str]] = None
        self.reader_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._running = False
        self._current_command: Optional[str] = None
        self._current_marker: Optional[str] = None
        self._current_started_at: float = 0.0
        self._current_output_lines: List[str] = []

    def start(self) -> None:
        if self.proc and self.proc.poll() is None:
            return
        shell_cmd: List[str]
        if os.name == "nt":
            shell_cmd = ["powershell", "-NoLogo", "-NoProfile", "-NoExit", "-Command", "-"]
        else:
            shell_bin = os.environ.get("SHELL", "/bin/bash")
            shell_cmd = [shell_bin]
        self.proc = subprocess.Popen(
            shell_cmd,
            cwd=str(self.workspace_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._running = True
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()
        self.bus.emit(
            "terminal_output",
            {"line": f"[shell] Started in {self.workspace_root}"},
        )

    def stop(self) -> None:
        self._running = False
        if self.proc and self.proc.poll() is None:
            try:
                if self.proc.stdin:
                    self.proc.stdin.write("exit\n")
                    self.proc.stdin.flush()
            except Exception:
                pass
            try:
                self.proc.terminate()
            except Exception:
                pass

    def execute(self, command: str) -> None:
        cleaned = (command or "").strip()
        if not cleaned:
            return
        with self._lock:
            if not self.proc or self.proc.poll() is not None:
                self.start()
            if not self.proc or not self.proc.stdin:
                self.bus.emit(
                    "command_finished",
                    {
                        "command": cleaned,
                        "elapsed": 0.0,
                        "success": False,
                        "output": "Shell process is unavailable.",
                        "exitCode": -1,
                    },
                )
                return
            marker_id = uuid.uuid4().hex
            self._current_command = cleaned
            self._current_marker = marker_id
            self._current_started_at = time.time()
            self._current_output_lines = []
            self.bus.emit("command_started", {"command": cleaned})
            if os.name == "nt":
                wrapped = f"{cleaned}\nWrite-Output \"{self.MARKER_PREFIX}{marker_id}:$LASTEXITCODE\"\n"
            else:
                wrapped = f"{cleaned}\nprintf \"{self.MARKER_PREFIX}{marker_id}:%s\\n\" $?\n"
            self.proc.stdin.write(wrapped)
            self.proc.stdin.flush()

    def _read_loop(self) -> None:
        if not self.proc or not self.proc.stdout:
            return
        while self._running and self.proc and self.proc.stdout:
            line = self.proc.stdout.readline()
            if line == "":
                break
            clean = strip_ansi(line.rstrip("\n"))
            if not clean:
                continue
            with self._lock:
                marker = self._current_marker
                if marker and clean.startswith(f"{self.MARKER_PREFIX}{marker}:"):
                    exit_part = clean.split(":", 2)[-1]
                    try:
                        exit_code = int(exit_part)
                    except Exception:
                        exit_code = -1
                    command = self._current_command or ""
                    elapsed = max(0.0, time.time() - self._current_started_at)
                    output = "\n".join(self._current_output_lines).strip()
                    self.bus.emit(
                        "command_finished",
                        {
                            "command": command,
                            "elapsed": elapsed,
                            "success": exit_code == 0,
                            "output": output,
                            "exitCode": exit_code,
                        },
                    )
                    self._current_command = None
                    self._current_marker = None
                    self._current_started_at = 0.0
                    self._current_output_lines = []
                    continue

                self.bus.emit("terminal_output", {"line": clean})
                if self._current_marker:
                    self._current_output_lines.append(clean)


async def run_server(
    host: str,
    port: int,
    workspace_root: Path,
    config_path: str,
    runtime_overrides: Optional[Dict[str, Any]] = None,
    conversation_id: Optional[str] = None,
) -> None:
    bus = EventBus()
    runtime = GUIBridgeRuntime(
        workspace_root=workspace_root,
        config_path=config_path,
        bus=bus,
        runtime_overrides=runtime_overrides,
    )

    async def handler(websocket: Any) -> None:
        bus.clients.add(websocket)
        bus.emit("session_status", {"status": "connected"})
        try:
            async for message in websocket:
                data = json.loads(message)
                command = data.get("command")
                payload = data.get("payload", {})
                if command == "ping":
                    await websocket.send(json.dumps({"type": "pong", "timestamp": time.time()}))
                elif command == "submit_prompt":
                    runtime.run_prompt(payload.get("prompt", "").strip(), payload.get("mode", "agent"))
                elif command == "approval_response":
                    runtime.approval_manager.respond(
                        str(payload.get("id", "")),
                        bool(payload.get("approved")),
                    )
                elif command == "set_execution_mode":
                    runtime.set_execution_mode(str(payload.get("mode", "autonomous")))
                elif command == "list_mcp":
                    runtime.list_mcp_status()
                elif command == "reload_mcp":
                    runtime.reload_mcp()
                elif command == "refresh_tree":
                    bus.emit(
                        "file_tree_snapshot",
                        {
                            "rootPath": str(workspace_root),
                            "nodes": bus.snapshot_tree(workspace_root),
                        },
                    )
                elif command == "terminal_input":
                    runtime.execute_terminal_input(payload.get("input", ""))
                elif command == "cancel_current_task":
                    bus.emit(
                        "error",
                        {
                            "level": "warning",
                            "message": "Cancel is not yet supported by CLI runtime.",
                        },
                    )
        finally:
            bus.clients.discard(websocket)

    async with serve(handler, host, port) as server:
        bus.loop = asyncio.get_running_loop()
        sockets = getattr(server, "sockets", []) or []
        actual_port = sockets[0].getsockname()[1] if sockets else port
        # Tell Electron the WebSocket port immediately; load RAYS in the background.
        print(json.dumps({"event": "bridge_ready", "port": actual_port}), flush=True)
        bus.emit("session_status", {"status": "starting", "workspaceRoot": str(workspace_root)})

        def _initialize_runtime() -> None:
            try:
                runtime.initialize(conversation_id=conversation_id)
                runtime.emit_restored_chat_history()
            except Exception as exc:
                traceback.print_exc()
                bus.emit(
                    "error",
                    {"level": "fatal", "message": f"Failed to start RAYS engine: {exc}"},
                )
                print(
                    json.dumps({"event": "bridge_init_failed", "message": str(exc)}),
                    flush=True,
                )

        await asyncio.to_thread(_initialize_runtime)
        await asyncio.Future()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAYS GUI websocket bridge")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--workspace", type=str, required=True)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--runtime_overrides", type=str, default="")
    parser.add_argument("--conversation_id", type=str, default=None)
    return parser.parse_args()


def main() -> None:
    try:
        # Load RAYS on the main thread before worker threads import rays_ui (signal handlers).
        os.environ.setdefault("RAYS_GUI_BRIDGE", "1")
        from rays_core import rays_ui as _rays_ui  # noqa: F401
        from rays_core.rays_main import RAYS as _RAYS  # noqa: F401

        args = parse_args()
        workspace_root = Path(args.workspace).expanduser().resolve()
        if not workspace_root.exists():
            raise FileNotFoundError(f"Workspace path does not exist: {workspace_root}")
        config_path = str(resolve_config_path(args.config))
        runtime_overrides: Dict[str, Any] = {}
        if args.runtime_overrides:
            runtime_overrides = json.loads(args.runtime_overrides)
        asyncio.run(
            run_server(
                args.host,
                args.port,
                workspace_root,
                config_path,
                runtime_overrides=runtime_overrides,
                conversation_id=args.conversation_id,
            )
        )
    except Exception as exc:
        traceback.print_exc()
        print(json.dumps({"event": "bridge_fatal", "message": str(exc)}), flush=True)
        raise


if __name__ == "__main__":
    main()
