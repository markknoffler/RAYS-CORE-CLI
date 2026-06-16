import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./src/test",
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:8080",
    trace: "retain-on-failure",
  },
});
