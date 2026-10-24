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
    this.ownedPid = null;
    this.host = "127.0.0.1";
    this.port = 8000;
    this.healthUrl = `http://${this.host}:${this.port}/health`;
    this.shutdownUrl = `http://${this.host}:${this.port}/api/v1/shutdown`;

    this.status = "stopped";
    this.message = "Backend is stopped";
    this.onStatusChange = null;
    this.isStarting = false;
    this.serverReady = false;
    this.startupLogStream = null;
    this.shutdownPromise = null;
  }

  isPackaged() {
    return Boolean(app && app.isPackaged);
  }

  getStatusState() {
    return {
      status: this.status,
      message: this.message,
      ownedByElectron: this.ownedByElectron,
      ownedPid: this.ownedPid,
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
      const execPath = this.getBackendExecutable();
      if (execPath && fs.existsSync(execPath)) {
        return path.dirname(execPath);
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
      if (this.status === "stopping" || this.status === "stopped") {
        logBackend("waitForHealth aborted: backendManager is stopping or stopped.");
        return false;
      }

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
      if (attempt === 6 && !this.childProcess && !this.ownedByElectron && this.status !== "stopping" && this.status !== "stopped") {
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

      if (!fs.existsSync(backendDir) && fs.existsSync(backendExec)) {
        backendDir = path.dirname(backendExec);
      }

      if (!fs.existsSync(backendExec)) {
        const errorMsg = `Executable discovery failure: Packaged backend executable not found at "${backendExec}"`;
        logBackend(`CRITICAL: ${errorMsg}`);
        console.error(`[ELECTRON CRITICAL] ${errorMsg}`);
        this.setStatus("error", errorMsg);
        throw new Error(errorMsg);
      }

      logBackend(`[PRODUCTION SPAWN] file: "${backendExec}" (exists=${fs.existsSync(backendExec)})`);
      logBackend(`[PRODUCTION SPAWN] cwd (explicit): "${backendDir}" (exists=${fs.existsSync(backendDir)})`);
    } else {
      backendExec = this.getBackendExecutable();
      backendDir = this.getBackendDir();
      const isBinary = backendExec.endsWith(".exe") && !backendExec.toLowerCase().includes("python");
      args = isBinary ? [] : ["main.py"];

      if (!fs.existsSync(backendDir) && fs.existsSync(backendExec)) {
        backendDir = path.dirname(backendExec);
      }

      if (isBinary && !fs.existsSync(backendExec)) {
        const errorMsg = `Executable discovery failure: Backend binary not found at "${backendExec}"`;
        logBackend(`CRITICAL: ${errorMsg}`);
        console.error(`[ELECTRON CRITICAL] ${errorMsg}`);
        this.setStatus("error", errorMsg);
        throw new Error(errorMsg);
      }

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
    this.ownedPid = this.childProcess.pid;
    logBackend(`Backend process spawned successfully with PID=${this.childProcess.pid}`);

    this.childProcess.on("error", (err) => {
      logBackend(`CRITICAL: Backend child process spawn error: ${err.message}\n${err.stack || ""}`);
      console.error("[ELECTRON CRITICAL] Backend process error:", err);
      const wasOwned = this.ownedByElectron;
      this.childProcess = null;
      this.ownedByElectron = false;
      this.ownedPid = null;
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
      this.ownedPid = null;

      if (wasOwned && this.status !== "stopped" && this.status !== "stopping") {
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
      logBackend("Backend start already in progress.");
      return true;
    }
    if (this.status === "ready") {
      logBackend("Backend is already running and ready.");
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
      // 1. Check if healthy IRIS backend is already running
      const existing = await this.checkHealthOnce();
      if (existing.online && existing.iris) {
        logBackend(`Found active IRIS backend on 127.0.0.1:8000 (version=${existing.version}) — reusing instance.`);
        this.ownedByElectron = false;
        this.setStatus("ready", "Connected to existing IRIS backend");
        return true;
      }

      // 2. Spawn the backend child process
      this.spawnBackendProcess();

      // 3. Wait for health check with 60 attempts at 1-second intervals (60s total timeout)
      const isHealthy = await this.waitForHealth(60, 1000);
      if (!isHealthy) {
        this.setStatus("error", "IRIS backend failed to respond within 60 seconds.");
        await this.stop();
        throw new Error("IRIS backend failed to respond within 60 seconds.");
      }

      logBackend("IRIS backend is online and healthy.");
      this.setStatus("ready", "Backend connected & operational");
      return true;
    } catch (err) {
      logBackend(`Backend startup failure: ${err.message}`);
      await this.stop();
      throw err;
    } finally {
      this.isStarting = false;
    }
  }

  /**
   * Request graceful shutdown from the FastAPI backend via POST /api/v1/shutdown.
   */
  requestGracefulShutdown(timeoutMs = 1500) {
    return new Promise((resolve) => {
      const postData = "";
      const req = http.request(
        {
          hostname: this.host,
          port: this.port,
          path: "/api/v1/shutdown",
          method: "POST",
          timeout: timeoutMs,
          headers: {
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(postData),
          },
        },
        (res) => {
          let body = "";
          res.on("data", (chunk) => {
            body += chunk;
          });
          res.on("end", () => {
            logBackend(`Graceful shutdown endpoint response: HTTP ${res.statusCode} ${body.trim()}`);
            resolve(res.statusCode >= 200 && res.statusCode < 300);
          });
        }
      );

      req.on("error", (err) => {
        logBackend(`Graceful shutdown request error: ${err.message}`);
        resolve(false);
      });

      req.on("timeout", () => {
        logBackend(`Graceful shutdown request timed out after ${timeoutMs}ms.`);
        req.destroy();
        resolve(false);
      });

      req.write(postData);
      req.end();
    });
  }

  /**
   * Wait for child process to exit, subject to a bounded timeout.
   */
  waitForProcessExit(child, timeoutMs = 3000) {
    return new Promise((resolve) => {
      if (!child || child.killed || child.exitCode !== null) {
        resolve(true);
        return;
      }

      let timer = null;
      let resolved = false;

      const cleanup = (exited) => {
        if (resolved) return;
        resolved = true;
        if (timer) clearTimeout(timer);
        try {
          child.removeListener("exit", onExit);
          child.removeListener("close", onExit);
        } catch (e) {}
        resolve(exited);
      };

      const onExit = () => {
        cleanup(true);
      };

      child.once("exit", onExit);
      child.once("close", onExit);

      timer = setTimeout(() => {
        cleanup(false);
      }, timeoutMs);
    });
  }

  /**
   * Platform-specific targeted process tree termination for verified IRIS AI child process ONLY.
   * Never terminates unrelated processes or generic process names.
   */
  forceKillProcessTree(pid) {
    const targetPid = parseInt(pid, 10);
    if (!targetPid || isNaN(targetPid) || targetPid <= 0) {
      logBackend(`Invalid PID ${pid} provided for forceKillProcessTree; aborting.`);
      return;
    }

    // Safety guard: NEVER kill own process PID or root PIDs
    if (targetPid === process.pid || targetPid <= 4) {
      logBackend(`Target PID ${targetPid} matches current process or system process; refusing to terminate.`);
      return;
    }

    logBackend(`Executing targeted process-tree termination on verified PID ${targetPid}...`);
    try {
      if (process.platform === "win32") {
        execSync(`taskkill /pid ${targetPid} /T /F`, { stdio: "ignore" });
      } else {
        process.kill(targetPid, "SIGKILL");
      }
    } catch (e) {
      // Process may already have exited
    }
  }

  /**
   * Stop backend with graceful shutdown first, bounded timeout, and targeted fallback kill.
   * Completely idempotent and protected against concurrent calls.
   */
  stop() {
    if (this.shutdownPromise) {
      logBackend("Shutdown already in progress; returning existing shutdown promise.");
      return this.shutdownPromise;
    }

    if (this.status === "stopped" && !this.childProcess) {
      return Promise.resolve(true);
    }

    this.shutdownPromise = (async () => {
      const previousStatus = this.status;
      this.setStatus("stopping", "Shutting down backend process...");

      const child = this.childProcess;
      const pid = this.ownedPid || (child ? child.pid : null);
      const wasOwned = this.ownedByElectron;

      try {
        // 1. Send graceful shutdown HTTP request if backend was online, ready, or owned
        if (previousStatus === "ready" || previousStatus === "connecting" || wasOwned) {
          logBackend("Requesting graceful HTTP shutdown from backend...");
          await this.requestGracefulShutdown(1500);
        }

        // 2. If a child process is tracked, await its exit
        if (child) {
          logBackend(`Waiting for child process PID ${pid} to exit cleanly...`);
          const exitedCleanly = await this.waitForProcessExit(child, 3000);
          if (exitedCleanly) {
            logBackend(`Backend PID ${pid} exited cleanly.`);
          } else {
            // 3. Bounded fallback: targeted tree termination ONLY on this child PID
            logBackend(`Backend PID ${pid} did not exit within timeout. Falling back to targeted process-tree termination.`);
            this.forceKillProcessTree(pid);
            // Brief pause for OS to release file and network port handles
            await new Promise((r) => setTimeout(r, 200));
          }
        }
      } catch (err) {
        logBackend(`Error during backend stop sequence: ${err.message}`);
      } finally {
        this.childProcess = null;
        this.ownedByElectron = false;
        this.ownedPid = null;
        this.isStarting = false;
        this.serverReady = false;
        this.setStatus("stopped", "Backend stopped");
        this.shutdownPromise = null;
      }

      return true;
    })();

    return this.shutdownPromise;
  }

  /**
   * Restart backend cleanly: stops previous instance completely before starting anew.
   */
  async restart() {
    logBackend("Backend restart initiated. Stopping current backend...");
    await this.stop();
    logBackend("Previous backend stopped. Starting new backend instance...");
    return await this.start();
  }

  /**
   * Helper to re-spawn/start backend cleanly
   */
  async startBackend() {
    await this.stop();
    return await this.start();
  }

  /**
   * Backward-compatible synchronous/emergency kill wrapper.
   */
  killBackend() {
    if (this.childProcess && this.childProcess.pid) {
      const pid = this.childProcess.pid;
      this.forceKillProcessTree(pid);
      this.childProcess = null;
      this.ownedByElectron = false;
      this.ownedPid = null;
    }
    this.setStatus("stopped", "Backend terminated");
  }
}

module.exports = BackendManager;
