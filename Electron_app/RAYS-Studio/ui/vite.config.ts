import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { spawn, ChildProcessWithoutNullStreams, execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { promisify } from "node:util";
import fs from "node:fs/promises";

const execFileAsync = promisify(execFile);

type BackendSession = {
  id: string;
  process: ChildProcessWithoutNullStreams;
  wsPort: number;
  workspacePath: string;
};

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  base: "./",
  server: {
    host: "127.0.0.1",
    port: 8080,
    hmr: {
      overlay: true,
    },
  },
  plugins: [
    react(),
    {
      name: "rays-session-manager",
      configureServer(server) {
        const sessions = new Map<string, BackendSession>();
        const cliRoot = path.resolve(__dirname, "..");
        const pythonPath = [
          path.join(cliRoot, "src"),
          path.join(cliRoot, "bridge/src"),
          process.env.PYTHONPATH || "",
        ]
          .filter(Boolean)
          .join(path.delimiter);

        const stopSession = (sessionId: string) => {
          const session = sessions.get(sessionId);
          if (!session) return false;
          session.process.kill("SIGTERM");
          sessions.delete(sessionId);
          return true;
        };

        server.httpServer?.on("close", () => {
          for (const sessionId of sessions.keys()) {
            stopSession(sessionId);
          }
        });

        server.middlewares.use("/api/session/start", (req, res) => {
          if (req.method !== "POST") {
            res.statusCode = 405;
            res.end("Method not allowed");
            return;
          }

          let body = "";
          req.on("data", (chunk) => {
            body += chunk.toString("utf8");
          });
          req.on("end", () => {
            try {
              const parsed = JSON.parse(body || "{}");
              const workspacePath = String(parsed.workspacePath || "").trim();
              const runtimeOverrides = parsed.runtimeOverrides || {};
              const conversationId = parsed.conversationId
                ? String(parsed.conversationId)
                : undefined;
              if (!workspacePath) {
                res.statusCode = 400;
                res.end(JSON.stringify({ error: "workspacePath is required" }));
                return;
              }

              const sessionId = randomUUID();
              const command = process.platform === "win32" ? "python" : "python3";
              const bridgeArgs = [
                "-m",
                "rays_bridge.ws_bridge",
                "--workspace",
                workspacePath,
                "--port",
                "0",
                "--runtime_overrides",
                JSON.stringify(runtimeOverrides),
              ];
              if (conversationId) {
                bridgeArgs.push("--conversation_id", conversationId);
              }
              const child = spawn(command, bridgeArgs, {
                cwd: cliRoot,
                env: { ...process.env, PYTHONPATH: pythonPath },
              });

              let settled = false;
              const timeout = setTimeout(() => {
                if (settled) return;
                settled = true;
                child.kill("SIGTERM");
                res.statusCode = 504;
                res.end(JSON.stringify({ error: "Bridge startup timeout" }));
              }, 15000);

              const onFail = (errorMessage: string) => {
                if (settled) return;
                settled = true;
                clearTimeout(timeout);
                res.statusCode = 500;
                res.end(JSON.stringify({ error: errorMessage }));
              };

              child.stderr.on("data", (chunk) => {
                const text = chunk.toString("utf8").trim();
                if (!text) return;
                // Do not fail immediately on stderr output (warnings are common).
                // Startup failure is determined by timeout or early process exit.
                console.warn("[rays-session-manager][bridge stderr]", text);
              });

              child.stdout.on("data", (chunk) => {
                const lines = chunk.toString("utf8").split("\n");
                for (const line of lines) {
                  if (!line.trim()) continue;
                  try {
                    const parsedLine = JSON.parse(line);
                    if (parsedLine.event === "bridge_ready" && typeof parsedLine.port === "number") {
                      if (settled) return;
                      settled = true;
                      clearTimeout(timeout);
                      sessions.set(sessionId, {
                        id: sessionId,
                        process: child,
                        wsPort: parsedLine.port,
                        workspacePath,
                      });
                      res.setHeader("content-type", "application/json");
                      res.end(JSON.stringify({ sessionId, wsPort: parsedLine.port }));
                      return;
                    }
                  } catch {
                    // Ignore non-JSON lines.
                  }
                }
              });

              child.on("error", (err) => {
                onFail(err.message);
              });
              child.on("exit", (code) => {
                if (!settled) {
                  onFail(`Bridge exited before ready (code: ${code ?? "unknown"})`);
                }
              });
            } catch (error) {
              res.statusCode = 400;
              res.end(JSON.stringify({ error: "Invalid JSON body" }));
            }
          });
        });

        server.middlewares.use("/api/session/stop", (req, res) => {
          if (req.method !== "POST") {
            res.statusCode = 405;
            res.end("Method not allowed");
            return;
          }
          let body = "";
          req.on("data", (chunk) => {
            body += chunk.toString("utf8");
          });
          req.on("end", () => {
            try {
              const parsed = JSON.parse(body || "{}");
              const sessionId = String(parsed.sessionId || "");
              const stopped = stopSession(sessionId);
              res.setHeader("content-type", "application/json");
              res.end(JSON.stringify({ stopped }));
            } catch {
              res.statusCode = 400;
              res.end(JSON.stringify({ error: "Invalid JSON body" }));
            }
          });
        });

        server.middlewares.use("/api/file/read", async (req, res) => {
          if (req.method !== "POST") {
            res.statusCode = 405;
            res.end("Method not allowed");
            return;
          }
          let body = "";
          req.on("data", (chunk) => {
            body += chunk.toString("utf8");
          });
          req.on("end", async () => {
            try {
              const parsed = JSON.parse(body || "{}");
              const workspaceRoot = String(parsed.workspaceRoot || "");
              const relativePath = String(parsed.relativePath || "");
              if (!workspaceRoot || !relativePath) {
                res.statusCode = 400;
                res.end(JSON.stringify({ error: "workspaceRoot and relativePath are required" }));
                return;
              }
              const normalizedRoot = path.resolve(workspaceRoot);
              const resolvedPath = path.resolve(normalizedRoot, relativePath);
              if (!resolvedPath.startsWith(normalizedRoot)) {
                res.statusCode = 400;
                res.end(JSON.stringify({ error: "Invalid file path" }));
                return;
              }
              const content = await fs.readFile(resolvedPath, "utf8");
              res.setHeader("content-type", "application/json");
              res.end(JSON.stringify({ content }));
            } catch (error) {
              res.statusCode = 500;
              res.end(JSON.stringify({ error: "Failed to read file" }));
            }
          });
        });

        server.middlewares.use("/api/system/select-folder", async (req, res) => {
          if (req.method !== "POST") {
            res.statusCode = 405;
            res.end("Method not allowed");
            return;
          }
          try {
            let folderPath = "";
            if (process.platform === "darwin") {
              const { stdout } = await execFileAsync("osascript", [
                "-e",
                'POSIX path of (choose folder with prompt "Select workspace folder for RAYS")',
              ]);
              folderPath = stdout.trim();
            } else if (process.platform === "win32") {
              const script = [
                "Add-Type -AssemblyName System.Windows.Forms",
                "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog",
                '$dialog.Description = "Select workspace folder for RAYS"',
                "$dialog.ShowNewFolderButton = $false",
                "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {",
                "  Write-Output $dialog.SelectedPath",
                "}",
              ].join(";");
              const { stdout } = await execFileAsync("powershell", ["-NoProfile", "-Command", script]);
              folderPath = stdout.trim();
            } else {
              try {
                const { stdout } = await execFileAsync("zenity", [
                  "--file-selection",
                  "--directory",
                  "--title=Select workspace folder for RAYS",
                ]);
                folderPath = stdout.trim();
              } catch {
                const { stdout } = await execFileAsync("kdialog", [
                  "--getexistingdirectory",
                  ".",
                  "Select workspace folder for RAYS",
                ]);
                folderPath = stdout.trim();
              }
            }
            res.setHeader("content-type", "application/json");
            res.end(JSON.stringify({ folderPath }));
          } catch {
            res.statusCode = 500;
            res.end(JSON.stringify({ error: "Folder selection failed or was cancelled." }));
          }
        });
      },
    },
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
