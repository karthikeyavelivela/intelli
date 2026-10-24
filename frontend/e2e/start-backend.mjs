// Starts an isolated API (own SQLite DB + data dir) for Playwright, seeded with demo data.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const work = path.join(tmpdir(), "intellimetrics-e2e");
rmSync(work, { recursive: true, force: true });
mkdirSync(work, { recursive: true });
const venv = path.join(root, "backend", ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const py = existsSync(venv) ? venv : process.platform === "win32" ? "python" : "python3";
const port = process.env.E2E_API_PORT || "8100";
const posix = work.split(path.sep).join("/");
const child = spawn(py, ["-m", "uvicorn", "app.main:app", "--port", port, "--host", "127.0.0.1"], {
  cwd: path.join(root, "backend"),
  stdio: "inherit",
  env: {
    ...process.env,
    ENV: "development",
    DATABASE_URL: `sqlite:///${posix}/e2e.db`,
    DATA_DIR: path.join(work, "datasets"),
    AUTO_SEED: "true",
    FRONTEND_URL: `http://127.0.0.1:${process.env.E2E_WEB_PORT || "5273"}`,
    RATE_LIMIT_ENABLED: "false",
    AI_PROVIDER: "none",
    USE_CELERY: "false",
  },
});
child.on("exit", (c) => process.exit(c ?? 0));
for (const s of ["SIGINT", "SIGTERM"]) process.on(s, () => child.kill());
