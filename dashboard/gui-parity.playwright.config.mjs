import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

function findRepositoryRoot(start) {
  let current = start;
  while (current !== path.dirname(current)) {
    if (fs.existsSync(path.join(current, ".federation", "gui-capabilities.json"))) {
      return current;
    }
    current = path.dirname(current);
  }
  throw new Error("Could not locate .federation/gui-capabilities.json");
}

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = findRepositoryRoot(frontendRoot);
const frontendPort = process.env.GUI_FRONTEND_PORT || "5173";
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
const backendUrl = "http://127.0.0.1:8000";

export default defineConfig({
  testDir: "./tests",
  // Array, not a bare string: a second spec file must not be silently
  // dropped from collection the way it would be with a single-filename match.
  testMatch: ["gui-parity.spec.mjs"],
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI
    ? [["line"], ["html", { outputFolder: "playwright-report/gui-parity", open: "never" }]]
    : "line",
  use: {
    baseURL: frontendUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium-gui-parity",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "python3 -m uvicorn server.backend.main:app --host 127.0.0.1 --port 8000",
      cwd: repositoryRoot,
      env: {
        ...process.env,
        ALLOWED_ORIGINS: frontendUrl,
        MONEYSWEEP_CORS_ORIGINS: frontendUrl,
        PYTHONPATH: [
          path.join(repositoryRoot, "src"),
          repositoryRoot,
          process.env.PYTHONPATH,
        ]
          .filter(Boolean)
          .join(path.delimiter),
      },
      url: `${backendUrl}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      cwd: frontendRoot,
      env: {
        ...process.env,
        VITE_API_BASE: backendUrl,
      },
      url: frontendUrl,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
