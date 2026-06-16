export const MCP_BLENDER_EXAMPLE = {
  mcp_servers: [
    {
      name: "blender",
      description:
        "Enables prompt-assisted 3D modeling, scene creation, and manipulation in Blender via Python code execution.",
      command: "uvx",
      args: ["--python", "3.11", "blender-mcp"],
      env: {
        BLENDER_HOST: "localhost",
        BLENDER_PORT: "9876",
        DISABLE_TELEMETRY: "true",
        UV_PYTHON_PREFERENCE: "only-managed",
      },
      enabled: true,
      quiet: false,
    },
  ],
} as const;

export const MCP_EXAMPLE_JSON = JSON.stringify(MCP_BLENDER_EXAMPLE, null, 2);

export const MCP_SINGLE_SERVER_EXAMPLE = JSON.stringify(MCP_BLENDER_EXAMPLE.mcp_servers[0], null, 2);
