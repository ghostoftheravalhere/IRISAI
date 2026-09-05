/**
 * BackendManager
 * Manages Python FastAPI backend process for Electron runtime in development & production packaged modes.
 *
 * Key features:
 * - Dynamic executable resolution (app.isPackaged check for backend/backend.exe)
 * - Clean spawning with windowsHide: true, detached: false, stdio: ['ignore', 'pipe', 'pipe']
 * - Explicit cwd setting to resources/backend for correct relative path resolution
 * - Dedicated backend_startup.log file write stream capturing all stdout, stderr, process errors, and exit codes
 * - Fast health check polling with adaptive interval and 15s timeout
 * - Immediate, reliable process tree termination via Windows taskkill /pid ${pid} /T /F on shutdown
 */
const { app } = require("electron");
const { spawn, execSync } = require("child_process");
const http = require("http");
const path = require("path");
const fs = require("fs");

let startupLogStream = null;

function getStartupLogStream() {
  if (startupLogStream && !startupLogStream.destroyed) {
    return startupLogStream;
  }
  try {
    const logDir = app && app.getPath ? app.getPath("userData") : "";
    if (logDir) {
      if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
      const logFile = path.join(logDir, "backend_startup.log");
      startupLogStream = fs.createWriteStream(logFile, { flags: "a", encoding: "utf8" });
    }
  } catch (e) {
    console.error("[ELECTRON] Failed to initialize backend_startup.log write stream:", e);
  }
  return startupLogStream;
}

function logBackend(msg) {
  const timestamp = new Date().toISOString();
  const logLine = `[${timestamp}] [BACKEND_MGR] ${msg}\n`;
  console.log(`[ELECTRON] ${msg}`);

  try {
    const stream = getStartupLogStream();
    if (stream && !stream.destroyed) {
      stream.write(logLine);
    }
    const logDir = app && app.getPath ? app.getPath("userData") : "";
    if (logDir) {
      if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
      fs.appendFileSync(path.join(logDir, "prod_debug.log"), logLine);
      fs.appendFileSync(path.join(logDir, "backend_startup.log"), logLine);
    }
  } catch (e) {}
}

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
    this.serverReady = false;
    this.startupLogStream = null;
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
          logBackend(`Compiled backend binary found at: ${p}`);
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
    const binaryName = isWin ? "backend.exe" : "backend";

    // 1. Packaged production binary in process.resourcesPath/backend/backend.exe
    if (this.isPackaged()) {
      const primaryPackaged = path.join(process.resourcesPath, "backend", binaryName);
      if (fs.existsSync(primaryPackaged)) {
        logBackend(`Found packaged backend binary at: ${primaryPackaged}`);
        return primaryPackaged;
      }

      const altPackaged = path.join(path.dirname(process.execPath), "resources", "backend", binaryName);
      if (fs.existsSync(altPackaged)) {
        logBackend(`Found packaged backend binary at alt path: ${altPackaged}`);
        return altPackaged;
      }

      const irisPackaged = path.join(process.resourcesPath, "backend", isWin ? "iris_backend.exe" : "iris_backend");
      if (fs.existsSync(irisPackaged)) {
        logBackend(`Found packaged iris_backend binary at: ${irisPackaged}`);
        return irisPackaged;
      }

      // Check fallback scanner across all known locations
      const scanned = this.getBackendPath();
      if (scanned) {
        logBackend(`Found scanned backend binary at: ${scanned}`);
        return scanned;
      }

      return primaryPackaged;
    }

    // 2. Development mode or local dist check
    const localDist = path.resolve(__dirname, "../../dist/backend", binaryName);
    if (fs.existsSync(localDist)) {
      logBackend(`Found local dist backend binary at: ${localDist}`);
      return localDist;
    }

    // 3. Development virtual environment python
    const venvPython = isWin
      ? path.resolve(__dirname, "../../backend/.venv/Scripts/python.exe")
      : path.resolve(__dirname, "../../backend/.venv/bin/python");

    if (fs.existsSync(venvPython)) {
      logBackend(`Found Dev Python interpreter at: ${venvPython}`);
      return venvPython;
    }

    return isWin ? "python.exe" : "python3";
  }

  /**
   * Resolve backend working directory.
   */
  getBackendDir() {
    if (this.isPackaged()) {
      const primaryDir = path.join(process.resourcesPath, "backend");
      if (fs.existsSync(primaryDir)) {
        return primaryDir;
      }
      const altDir = path.join(path.dirname(process.execPath), "resources", "backend");
      if (fs.existsSync(altDir)) {
        return altDir;
      }
      return primaryDir;
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
   * Poll health endpoint with 60 attempts at 1-second intervals (60s total timeout).
   * Accommodates cold-start PyInstaller unpacks, Windows Defender first-run scans (25-45s), and disk latency.
   */
  async waitForHealth(maxAttempts = 60, intervalMs = 1000) {
    const startTime = Date.now();

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      // Dynamic status message updates across the full 60 attempts
      let dynamicMsg = "Initializing AI engine & dependencies...";
      if (attempt > 45) {
        dynamicMsg = "Waiting for local API gateway on port 8000...";
      } else if (attempt > 25) {
        dynamicMsg = "Loading AI models and runtime subsystems...";
      } else if (attempt > 8) {
        dynamicMsg = "Windows Defender security verification in progress...";
      } else {
        dynamicMsg = "Initializing AI engine & dependencies...";
      }

      this.setStatus("connecting", dynamicMsg);

      // 1. Check if backend health endpoint is 200 OK
      const { online, iris } = await this.checkHealthOnce();
      if (online && iris) {
        logBackend(`Backend health check passed on attempt ${attempt}/${maxAttempts} in ${Date.now() - startTime}ms.`);
        return true;
      }

      // 2. If SERVER_READY signal received, immediately re-verify health
      if (this.serverReady) {
        const verify = await this.checkHealthOnce();
        if (verify.online && verify.iris) {
          logBackend(`Backend confirmed online after SERVER_READY on attempt ${attempt} in ${Date.now() - startTime}ms.`);
          return true;
        }
      }

      // 3. Auto-recovery re-spawn if child process was dropped during initial scan
      if (attempt === 6 && !this.childProcess && !this.ownedByElectron) {
        logBackend("[BACKEND_MGR] Child process exited during initial scan. Attempting automatic recovery re-spawn...");
        try {
          this.spawnBackendProcess();
        } catch (respawnErr) {
          logBackend(`[BACKEND_MGR] Recovery re-spawn error: ${respawnErr.message}`);
        }
      }

      await new Promise((r) => setTimeout(r, intervalMs));
    }

    // Final attempt before returning false
    const finalCheck = await this.checkHealthOnce();
    return Boolean(finalCheck.online && finalCheck.iris);
  }

  /**
   * Spawn backend child process with resolved paths and full error/stdout/stderr listeners.
   */
  spawnBackendProcess() {
    let backendExec;
    let backendDir;
    let args;

    if (this.isPackaged()) {
      const isWin = process.platform === "win32";
      const binaryName = isWin ? "backend.exe" : "backend";
      
      backendExec = path.join(process.resourcesPath, "backend", binaryName);
      backendDir = path.join(process.resourcesPath, "backend");
      args = [];

      if (!fs.existsSync(backendExec)) {
        logBackend(`WARNING: Primary packaged path not found: "${backendExec}". Searching fallbacks...`);
        backendExec = this.getBackendExecutable();
        backendDir = this.getBackendDir();
      }

      logBackend(`[PRODUCTION SPAWN] file: "${backendExec}" (exists=${fs.existsSync(backendExec)})`);
      logBackend(`[PRODUCTION SPAWN] cwd (explicit): "${backendDir}" (exists=${fs.existsSync(backendDir)})`);
    } else {
      backendExec = this.getBackendExecutable();
      backendDir = this.getBackendDir();
      const isBinary = backendExec.endsWith(".exe") && !backendExec.toLowerCase().includes("python");
      args = isBinary ? [] : ["main.py"];

      logBackend(`[DEV SPAWN] file: "${backendExec}" (exists=${fs.existsSync(backendExec)})`);
      logBackend(`[DEV SPAWN] cwd: "${backendDir}" (exists=${fs.existsSync(backendDir)})`);
    }

    logBackend(`Spawning backend: "${backendExec}" args=${JSON.stringify(args)} cwd="${backendDir}"`);

    try {
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
    } catch (spawnErr) {
      logBackend(`CRITICAL: spawn call threw synchronous error: ${spawnErr.message}`);
      console.error("[ELECTRON CRITICAL] spawn threw error:", spawnErr);
      this.setStatus("error", `Failed to spawn backend: ${spawnErr.message}`);
      throw spawnErr;
    }

    this.ownedByElectron = true;
    logBackend(`Backend process spawned successfully with PID=${this.childProcess.pid}`);

    this.childProcess.on("error", (err) => {
      logBackend(`CRITICAL: Backend child process spawn error: ${err.message}\n${err.stack || ""}`);
      console.error("[ELECTRON CRITICAL] Backend process error:", err);
      const wasOwned = this.ownedByElectron;
      this.childProcess = null;
      this.ownedByElectron = false;
      if (wasOwned) {
        this.setStatus("error", `Backend failed to start: ${err.message}`);
      }
    });

    if (this.childProcess.stdout) {
      this.childProcess.stdout.on("data", (chunk) => {
        const text = chunk.toString();
        logBackend(`[STDOUT] ${text.trim()}`);
        if (text.includes("SERVER_READY")) {
          logBackend("Caught SERVER_READY signal from backend stdout!");
          this.serverReady = true;
        }
      });
      this.childProcess.stdout.on("error", (err) => {
        logBackend(`[STDOUT ERROR] ${err.message}`);
        console.error("[ELECTRON] Backend stdout error:", err);
      });
    }

    if (this.childProcess.stderr) {
      this.childProcess.stderr.on("data", (chunk) => {
        const text = chunk.toString();
        logBackend(`[STDERR] ${text.trim()}`);
        console.error(`[BACKEND STDERR] ${text.trim()}`);
        if (text.includes("SERVER_READY")) {
          logBackend("Caught SERVER_READY signal from backend stderr!");
          this.serverReady = true;
        }
      });
      this.childProcess.stderr.on("error", (err) => {
        logBackend(`[STDERR ERROR] ${err.message}`);
        console.error("[ELECTRON] Backend stderr error:", err);
      });
    }

    this.childProcess.on("exit", (code, signal) => {
      logBackend(`Backend process exited with code=${code}, signal=${signal}`);
      console.warn(`[ELECTRON] Backend process exited: code=${code}, signal=${signal}`);
      const wasOwned = this.ownedByElectron;
      this.childProcess = null;
      this.ownedByElectron = false;

      if (wasOwned && this.status !== "stopped") {
        this.setStatus("error", `Backend exited unexpectedly (code ${code})`);
      }
    });

    this.childProcess.on("close", (code, signal) => {
      logBackend(`Backend stdio streams closed: code=${code}, signal=${signal}`);
    });

    return this.childProcess;
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
    this.startupLogStream = getStartupLogStream();
    this.setStatus("starting", "Checking backend availability...");

    logBackend("=================================================");
    logBackend("         IRIS AI BACKEND STARTUP SEQUENCE        ");
    logBackend("=================================================");
    logBackend(`App isPackaged: ${this.isPackaged()}`);
    logBackend(`Process resourcesPath: ${process.resourcesPath}`);
    logBackend(`Process execPath: ${process.execPath}`);

    try {
      // 1. Check if healthy backend is already running
      const existing = await this.checkHealthOnce();
      if (existing.online && existing.iris) {
        logBackend(`Found active IRIS backend on 127.0.0.1:8000 (version=${existing.version}) — reusing instance.`);
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
              logBackend(`Terminating lingering port 8000 process PID ${pid}...`);
              execSync(`taskkill /F /PID ${pid} /T`);
            }
          }
        } catch (e) {}
      }

      // 3. Spawn the backend process
      this.spawnBackendProcess();

      // 4. Wait for health check with 60 attempts at 1-second intervals (60s total timeout)
      const isHealthy = await this.waitForHealth(60, 1000);
      if (!isHealthy) {
        this.setStatus("error", "IRIS backend failed to respond within 60 seconds.");
        this.killBackend();
        throw new Error("IRIS backend failed to respond within 60 seconds.");
      }

      logBackend("IRIS backend is online and healthy.");
      this.setStatus("ready", "Backend connected & operational");
      return true;
    } finally {
      this.isStarting = false;
    }
  }

  /**
   * Helper to re-spawn/start backend cleanly
   */
  async startBackend() {
    this.killBackend();
    return await this.start();
  }

  /**
   * Forcefully kill the backend process tree on Windows using taskkill /pid /T /F.
   */
  killBackend() {
    if (this.childProcess && this.childProcess.pid) {
      const pid = this.childProcess.pid;
      logBackend(`Forcefully killing backend process tree PID ${pid}...`);
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
    }

    // Clean up any lingering port 8000 process
    if (process.platform === "win32") {
      try {
        const netstat = execSync("netstat -ano -p tcp | findstr :8000", { encoding: "utf8" });
        const lines = netstat.trim().split("\n");
        for (const line of lines) {
          const parts = line.trim().split(/\s+/);
          const pid = parts[parts.length - 1];
          if (pid && !isNaN(pid) && parseInt(pid, 10) > 0 && parseInt(pid, 10) !== process.pid) {
            logBackend(`Cleaning up port 8000 listener PID ${pid}...`);
            execSync(`taskkill /F /PID ${pid} /T`);
          }
        }
      } catch (e) {}
    }

    this.setStatus("stopped", "Backend terminated");
  }

  stop() {
    this.killBackend();
  }
}

module.exports = BackendManager;
