/**
 * BackendManager
 * Manages Python FastAPI backend process for Electron runtime in development & production packaged modes.
 *
 * Key features:
 * - Dynamic executable resolution (app.isPackaged check for iris_backend/iris_backend.exe)
 * - Clean spawning with windowsHide: true, detached: false, stdio: 'ignore'
 * - Fast health check polling with 200ms interval and 20s timeout
 * - Immediate, reliable process tree termination via Windows taskkill /pid ${pid} /T /F on shutdown
 */
const { app } = require("electron");
const { spawn, execSync } = require("child_process");
const http = require("http");
const path = require("path");
const fs = require("fs");

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
    this.isStarting = false;
  }

  isPackaged() {
    return Boolean(app && app.isPackaged);
  }

  getStatusState() {
    return {
      status: this.status,
      message: this.message,
      ownedByElectron: this.ownedByElectron,
      port: this.port,
      isPackaged: this.isPackaged(),
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
   * Resolve backend executable path dynamically for dev vs production packaged mode.
   */
  /**
   * Robust scanner for backend.exe or iris_backend.exe across all extraction/installation layouts.
   */
  getBackendPath() {
    const isWin = process.platform === "win32";
    const execNames = isWin ? ["backend.exe", "iris_backend.exe"] : ["backend", "iris_backend"];

    for (const execName of execNames) {
      const possiblePaths = [
        path.join(process.resourcesPath, "backend", execName),
        path.join(process.resourcesPath, "iris_backend", execName),
        path.join(process.resourcesPath, execName),
        path.join(app && app.getAppPath ? app.getAppPath() : "", "..", "backend", execName),
        path.join(app && app.getAppPath ? app.getAppPath() : "", "..", "iris_backend", execName),
        path.join(path.dirname(app && app.getPath ? app.getPath("exe") : process.execPath), "resources", "backend", execName),
        path.join(path.dirname(app && app.getPath ? app.getPath("exe") : process.execPath), "resources", "iris_backend", execName),
        path.join(app && app.getPath ? app.getPath("userData") : "", "backend", execName),
        path.join(__dirname, "../../dist/backend", execName),
        path.join(__dirname, "../../dist/iris_backend", execName),
        path.resolve(__dirname, "../../dist/backend", execName),
        path.resolve(__dirname, "../../dist/iris_backend", execName),
      ];

      for (const p of possiblePaths) {
        if (p && fs.existsSync(p)) {
          console.log("[ELECTRON] Compiled backend binary found at:", p);
          return p;
        }
      }
    }

    return null;
  }

  /**
   * Resolve backend executable path (compiled standalone binary or dev python interpreter).
   */
  getBackendExecutable() {
    const isWin = process.platform === "win32";

    // 1. Packaged standalone binary (preferred for production)
    const binaryPath = this.getBackendPath();
    if (binaryPath) {
      return binaryPath;
    }

    if (this.isPackaged()) {
      // 2. Packaged virtual environment python.exe in extraResources (fallback)
      const packagedPython = isWin
        ? path.join(process.resourcesPath, "backend", ".venv", "Scripts", "python.exe")
        : path.join(process.resourcesPath, "backend", ".venv", "bin", "python");

      if (fs.existsSync(packagedPython)) {
        console.log("[ELECTRON] Packaged Python interpreter found at:", packagedPython);
        return packagedPython;
      }

      // 3. Alternative resources path for portable or unpacked layouts
      const altPython = isWin
        ? path.join(path.dirname(process.execPath), "resources", "backend", ".venv", "Scripts", "python.exe")
        : path.join(path.dirname(process.execPath), "resources", "backend", ".venv", "bin", "python");

      if (fs.existsSync(altPython)) {
        console.log("[ELECTRON] Packaged Python interpreter found at alt path:", altPython);
        return altPython;
      }
    }

    // 4. Development mode fallback: virtual environment python
    const venvPython = isWin
      ? path.resolve(__dirname, "../../backend/.venv/Scripts/python.exe")
      : path.resolve(__dirname, "../../backend/.venv/bin/python");

    if (fs.existsSync(venvPython)) {
      console.log("[ELECTRON] Dev Python interpreter found at:", venvPython);
      return venvPython;
    }

    return isWin ? "python.exe" : "python3";
  }

  /**
   * Resolve backend working directory.
   */
  getBackendDir() {
    if (this.isPackaged()) {
      const resourcesBackend = path.join(process.resourcesPath, "backend");
      if (fs.existsSync(resourcesBackend)) {
        return resourcesBackend;
      }
      const altResourcesBackend = path.join(path.dirname(process.execPath), "resources", "backend");
      if (fs.existsSync(altResourcesBackend)) {
        return altResourcesBackend;
      }
    }

    const execPath = this.getBackendExecutable();
    if (execPath && execPath.endsWith(".exe") && !execPath.toLowerCase().includes("python")) {
      return path.dirname(execPath);
    }
    return path.resolve(__dirname, "../../backend");
  }

  /**
   * Query GET http://127.0.0.1:8000/health
   */
  checkHealthOnce() {
    return new Promise((resolve) => {
      const req = http.get(this.healthUrl, { timeout: 1200 }, (res) => {
        let body = "";
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          if (res.statusCode === 200) {
            try {
              const data = JSON.parse(body);
              if (data && (data.status === "online" || data.status === "ok" || data.status === "HEALTHY")) {
                resolve({
                  online: true,
                  iris: true,
                  version: data.version,
                  executable: data.executable,
                  resolver: data.resolver,
                });
                return;
              }
            } catch (e) {}
            resolve({ online: true, iris: true });
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
   * Poll health endpoint with adaptive exponential backoff until healthy, SERVER_READY received, or timeout.
   * Accommodates cold-start PyInstaller unpacks, Windows Defender scans, and disk latency.
   */
  async waitForHealth(timeoutMs = 15000, initialIntervalMs = 300) {
    this.setStatus("connecting", "Initializing IRIS AI v2.4.5 (checking health)...");
    const startTime = Date.now();
    let currentInterval = initialIntervalMs;

    while (Date.now() - startTime < timeoutMs) {
      // 1. Check if backend health endpoint is 200 OK
      const { online, iris } = await this.checkHealthOnce();
      if (online && iris) {
        console.log(`[ELECTRON] Backend health check passed in ${Date.now() - startTime}ms.`);
        return true;
      }

      // 2. If SERVER_READY signal received, immediately re-verify health
      if (this.serverReady) {
        const verify = await this.checkHealthOnce();
        if (verify.online && verify.iris) {
          console.log(`[ELECTRON] Backend confirmed online after SERVER_READY in ${Date.now() - startTime}ms.`);
          return true;
        }
      }

      await new Promise((r) => setTimeout(r, currentInterval));
      currentInterval = Math.min(1000, Math.floor(currentInterval * 1.25));
    }

    // Final attempt before returning false
    const finalCheck = await this.checkHealthOnce();
    return Boolean(finalCheck.online && finalCheck.iris);
  }

  /**
   * Ensure backend is running before Electron window opens.
   */
  async start() {
    if (this.isStarting) {
      return true;
    }
    this.isStarting = true;
    this.serverReady = false;
    this.setStatus("starting", "Checking backend availability...");

    try {
      // 1. Check if healthy backend is already running
      const existing = await this.checkHealthOnce();
      if (existing.online && existing.iris) {
        console.log(`[ELECTRON] Found active IRIS backend on 127.0.0.1:8000 (version=${existing.version}) — reusing instance.`);
        this.ownedByElectron = false;
        this.setStatus("ready", "Connected to existing IRIS backend");
        return true;
      }

      // 2. Clean up any stale unresponsive port 8000 process
      if (process.platform === "win32") {
        try {
          const netstat = execSync("netstat -ano -p tcp | findstr :8000", { encoding: "utf8" });
          const lines = netstat.trim().split("\n");
          for (const line of lines) {
            const parts = line.trim().split(/\s+/);
            const pid = parts[parts.length - 1];
            if (pid && !isNaN(pid) && parseInt(pid, 10) > 0 && parseInt(pid, 10) !== process.pid) {
              console.log(`[ELECTRON] Terminating lingering port 8000 process PID ${pid}...`);
              execSync(`taskkill /F /PID ${pid} /T`);
            }
          }
        } catch (e) {}
      }

      // 3. Resolve executable and working directory
      const backendExec = this.getBackendExecutable();
      const backendDir = this.getBackendDir();
      const isBinary = backendExec.endsWith(".exe") && !backendExec.toLowerCase().includes("python");
      const args = isBinary ? [] : ["main.py"];

      console.log(`[ELECTRON] Spawning backend: "${backendExec}" (exists=${fs.existsSync(backendExec)}) in cwd: "${backendDir}"`);

      this.childProcess = spawn(backendExec, args, {
        cwd: backendDir,
        windowsHide: true,
        detached: false,
        stdio: ["ignore", "pipe", "pipe"],
        env: {
          ...process.env,
          PYTHONPATH: backendDir,
          PYTHONUNBUFFERED: "1",
          PYTHONIOENCODING: "utf-8",
          IRIS_RUNNING_IN_ELECTRON: "1",
        },
      });

      this.ownedByElectron = true;
      console.log(`[ELECTRON] Backend spawned with PID=${this.childProcess.pid}`);

      if (this.childProcess.stdout) {
        this.childProcess.stdout.on("data", (chunk) => {
          const text = chunk.toString();
          console.log(`[BACKEND STDOUT] ${text.trim()}`);
          if (text.includes("SERVER_READY")) {
            console.log("[ELECTRON] Caught SERVER_READY signal from backend stdout!");
            this.serverReady = true;
          }
        });
      }

      if (this.childProcess.stderr) {
        this.childProcess.stderr.on("data", (chunk) => {
          const text = chunk.toString();
          console.log(`[BACKEND STDERR] ${text.trim()}`);
          if (text.includes("SERVER_READY")) {
            console.log("[ELECTRON] Caught SERVER_READY signal from backend stderr!");
            this.serverReady = true;
          }
        });
      }

      this.childProcess.on("exit", (code, signal) => {
        console.log(`[ELECTRON] Backend process PID=${this.childProcess?.pid || "unknown"} exited with code ${code}, signal ${signal}`);
        const wasOwned = this.ownedByElectron;
        this.childProcess = null;
        this.ownedByElectron = false;

        if (wasOwned && this.status !== "stopped") {
          this.setStatus("error", `Backend exited unexpectedly (code ${code})`);
        }
      });

      // 4. Wait for health check with retries up to 15 seconds
      const isHealthy = await this.waitForHealth(15000, 300);
      if (!isHealthy) {
        this.setStatus("error", "IRIS backend failed to respond within 15 seconds.");
        this.killBackend();
        throw new Error("IRIS backend failed to respond within 15 seconds.");
      }

      console.log("[ELECTRON] IRIS backend is online and healthy.");
      this.setStatus("ready", "Backend connected & operational");
      return true;
    } finally {
      this.isStarting = false;
    }
  }

  /**
   * Forcefully kill the backend process tree on Windows using taskkill /pid /T /F.
   */
  killBackend() {
    if (this.childProcess && this.childProcess.pid) {
      const pid = this.childProcess.pid;
      console.log(`[ELECTRON] Forcefully killing backend process tree PID ${pid}...`);
      try {
        if (process.platform === "win32") {
          execSync(`taskkill /pid ${pid} /T /F`);
        } else {
          this.childProcess.kill("SIGKILL");
        }
      } catch (e) {
        // Process may already have terminated
      }
      this.childProcess = null;
      this.ownedByElectron = false;
      this.setStatus("stopped", "Backend stopped");
    }
  }

  /**
   * Stop backend process synchronously or gracefully.
   */
  async stop() {
    this.killBackend();
  }
}

module.exports = BackendManager;
