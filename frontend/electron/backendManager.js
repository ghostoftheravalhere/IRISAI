/**
 * BackendManager
 * Manages Python FastAPI backend process for Electron runtime in development mode.
 * Features:
 * - Pre-spawn check (reuses existing IRIS backend if 127.0.0.1:8000 is healthy)
 * - Subprocess spawning using backend/.venv/Scripts/python.exe (Windows) / backend/.venv/bin/python (POSIX)
 * - Health check polling (GET http://127.0.0.1:8000/health, 200ms poll interval, 15s timeout)
 * - Status lifecycle tracking (starting, connecting, ready, error, stopped, restarting)
 * - Stdout / Stderr stream piping prefixed with [PYTHON BACKEND]
 * - Graceful SIGINT/SIGTERM shutdown with 3s fallback SIGKILL on Electron quit
 * - Idempotent teardown protection against double-shutdown race conditions
 * - Safe process restart capability
 */
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

class BackendManager {
  constructor() {
    this.childProcess = null;
    this.ownedByElectron = false;
    this.host = "127.0.0.1";
    this.port = 8000;
    this.healthUrl = `http://${this.host}:${this.port}/health`;

    this.status = "stopped";
    this.message = "Backend is stopped";
    this.onStatusChange = null;
    this.stopPromise = null;
    this.isStarting = false;
  }

  getStatusState() {
    return {
      status: this.status,
      message: this.message,
      ownedByElectron: this.ownedByElectron,
      port: this.port,
    };
  }

  setStatus(newStatus, message = "") {
    this.status = newStatus;
    this.message = message;
    if (typeof this.onStatusChange === "function") {
      try {
        this.onStatusChange(this.getStatusState());
      } catch (e) {
        console.error("[ELECTRON] Error in onStatusChange callback:", e);
      }
    }
  }

  /**
   * Resolve Python executable path dynamically relative to __dirname.
   */
  getPythonExecutable() {
    const isWin = process.platform === "win32";
    const venvPython = isWin
      ? path.join(__dirname, "../../backend/.venv/Scripts/python.exe")
      : path.join(__dirname, "../../backend/.venv/bin/python");

    return venvPython;
  }

  /**
   * Resolve backend working directory.
   */
  getBackendDir() {
    return path.resolve(__dirname, "../../backend");
  }

  /**
   * Query GET http://127.0.0.1:8000/health
   */
  checkHealthOnce() {
    return new Promise((resolve) => {
      const req = http.get(this.healthUrl, { timeout: 1000 }, (res) => {
        let body = "";
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          if (res.statusCode === 200) {
            try {
              const data = JSON.parse(body);
              if (data && (data.status === "online" || data.status === "ok")) {
                resolve({ online: true, iris: true });
                return;
              }
            } catch (e) {
              // Ignore non-JSON body
            }
            resolve({ online: true, iris: false });
          } else {
            resolve({ online: false, iris: false });
          }
        });
      });

      req.on("error", () => {
        resolve({ online: false, iris: false });
      });

      req.on("timeout", () => {
        req.destroy();
        resolve({ online: false, iris: false });
      });
    });
  }

  /**
   * Poll health endpoint until healthy or timeout.
   */
  async waitForHealth(timeoutMs = 15000, intervalMs = 200) {
    this.setStatus("connecting", "Waiting for backend health check...");
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      const { online, iris } = await this.checkHealthOnce();
      if (online && iris) {
        return true;
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    return false;
  }

  /**
   * Ensure backend is running before Electron window opens.
   */
  async start() {
    if (this.isStarting) {
      return true;
    }
    this.isStarting = true;
    this.setStatus("starting", "Checking backend availability...");

    try {
      // 1. Check if backend is already running
      const existing = await this.checkHealthOnce();
      if (existing.online && existing.iris) {
        console.log("[ELECTRON] Found healthy existing IRIS backend on 127.0.0.1:8000 — reusing instance.");
        this.ownedByElectron = false;
        this.setStatus("ready", "Connected to existing IRIS backend");
        return true;
      }

      if (existing.online && !existing.iris) {
        const errMsg = `Port ${this.port} is occupied by a non-IRIS process.`;
        this.setStatus("error", errMsg);
        throw new Error(errMsg);
      }

      // 2. Spawn backend process
      const pythonExec = this.getPythonExecutable();
      const backendDir = this.getBackendDir();

      console.log(`[ELECTRON] Spawning IRIS backend: ${pythonExec} main.py in ${backendDir}`);

      this.childProcess = spawn(pythonExec, ["main.py"], {
        cwd: backendDir,
        env: { ...process.env, PYTHONUNBUFFERED: "1" },
        stdio: ["ignore", "pipe", "pipe"],
      });

      this.ownedByElectron = true;

      this.childProcess.stdout.on("data", (data) => {
        const lines = data.toString().trim().split("\n");
        lines.forEach((line) => {
          if (line) console.log(`[PYTHON BACKEND] ${line}`);
        });
      });

      this.childProcess.stderr.on("data", (data) => {
        const lines = data.toString().trim().split("\n");
        lines.forEach((line) => {
          if (line) console.error(`[PYTHON BACKEND] ${line}`);
        });
      });

      this.childProcess.on("exit", (code, signal) => {
        console.log(`[PYTHON BACKEND] Process exited with code ${code}, signal ${signal}`);
        const wasOwned = this.ownedByElectron;
        this.childProcess = null;
        this.ownedByElectron = false;

        if (wasOwned && this.status !== "restarting" && this.status !== "stopped") {
          this.setStatus("error", `Python backend exited unexpectedly (code ${code})`);
        }
      });

      // 3. Wait for health check
      const isHealthy = await this.waitForHealth(15000, 200);
      if (!isHealthy) {
        this.setStatus("error", "IRIS backend failed to become healthy within 15 seconds.");
        await this.stop();
        throw new Error("IRIS backend failed to become healthy within 15 seconds.");
      }

      console.log("[ELECTRON] IRIS backend is online and healthy.");
      this.setStatus("ready", "Backend connected & operational");
      return true;
    } finally {
      this.isStarting = false;
    }
  }

  /**
   * Safely restart Python backend process.
   */
  async restart() {
    console.log("[ELECTRON] Restarting backend process...");
    this.setStatus("restarting", "Restarting Python backend...");
    await this.stop();
    return await this.start();
  }

  /**
   * Stop child process gracefully upon Electron quit (Idempotent).
   */
  stop() {
    // Reused instance check: Electron does NOT terminate pre-existing processes
    if (!this.ownedByElectron || !this.childProcess) {
      this.setStatus("stopped", "Backend stopped");
      return Promise.resolve();
    }

    // Idempotent check: return existing pending stop promise if already in progress
    if (this.stopPromise) {
      return this.stopPromise;
    }

    console.log("[ELECTRON] Initiating graceful teardown of Python backend...");
    const proc = this.childProcess;

    this.stopPromise = new Promise((resolve) => {
      let resolved = false;

      const finish = () => {
        if (!resolved) {
          resolved = true;
          this.childProcess = null;
          this.ownedByElectron = false;
          this.stopPromise = null;
          this.setStatus("stopped", "Backend stopped");
          resolve();
        }
      };

      proc.once("exit", () => {
        console.log("[ELECTRON] Python backend process stopped cleanly.");
        finish();
      });

      // Send SIGINT for Python FastAPI graceful lifespan teardown
      try {
        proc.kill("SIGINT");
      } catch (e) {
        try {
          proc.kill("SIGTERM");
        } catch (err) {
          finish();
          return;
        }
      }

      // 3-second fallback timer before SIGKILL
      setTimeout(() => {
        if (!resolved && proc && !proc.killed) {
          console.warn("[ELECTRON] Python backend did not exit in 3s; sending SIGKILL...");
          try {
            proc.kill("SIGKILL");
          } catch (e) {}
          finish();
        }
      }, 3000);
    });

    return this.stopPromise;
  }
}

module.exports = BackendManager;
