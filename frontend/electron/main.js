/**
 * Electron Main Process
 * - Creates BrowserWindow
 * - Dev: loads Vite dev server + opens DevTools
 * - Prod: loads built dist/index.html
 * - Manages Python backend lifecycle via BackendManager & exposes IPC handlers
 * - Ensures synchronous, non-orphaning backend process termination on Windows exit
 */
const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const fs = require("fs");
const BackendManager = require("./backendManager");

const isDev = !app.isPackaged;
const backendManager = new BackendManager();
let mainWindow = null;
let isQuitting = false;

// Production Logging Helper
function logProd(msg) {
  const logLine = `[${new Date().toISOString()}] ${msg}\n`;
  console.log(msg);
  try {
    const logDir = app.getPath("userData");
    if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
    fs.appendFileSync(path.join(logDir, "prod_debug.log"), logLine);
  } catch (e) {}
}

function createWindow() {
  const preloadPath = path.join(__dirname, "preload.js");
  const distPath = path.join(__dirname, "../dist/index.html");
  const backendExecPath = backendManager.getBackendExecutable();

  logProd(`[PROD] app.isPackaged=${app.isPackaged}`);
  logProd(`[PROD] __dirname=${__dirname}`);
  logProd(`[PROD] process.resourcesPath=${process.resourcesPath}`);
  logProd(`[PROD] frontend path=${distPath}`);
  logProd(`[PROD] frontend exists=${fs.existsSync(distPath)}`);
  logProd(`[PROD] preload path=${preloadPath}`);
  logProd(`[PROD] preload exists=${fs.existsSync(preloadPath)}`);
  logProd(`[PROD] backend executable=${backendExecPath}`);
  logProd(`[PROD] backend exists=${fs.existsSync(backendExecPath)}`);

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: "#0a0a0f",
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Remove default menu bar
  mainWindow.setMenuBarVisibility(false);

  // Capture Renderer Console & Error Logs
  mainWindow.webContents.on("console-message", (event, level, message, line, sourceId) => {
    logProd(`[RENDERER CONSOLE] [Level ${level}] ${message} (${sourceId}:${line})`);
  });

  mainWindow.webContents.on("did-finish-load", () => {
    logProd(`[PROD] renderer load success: ${mainWindow.webContents.getURL()}`);
  });

  mainWindow.webContents.on("did-fail-load", (event, errorCode, errorDescription, validatedURL) => {
    logProd(`[PROD] renderer load failure (${errorCode}: ${errorDescription}) on ${validatedURL}`);
  });

  mainWindow.webContents.on("render-process-gone", (event, details) => {
    logProd(`[PROD CRITICAL] Render process gone: ${JSON.stringify(details)}`);
  });

  if (isDev && process.env.VITE_DEV_SERVER_URL !== "false") {
    const loadDevServer = async (retries = 10) => {
      for (let i = 0; i < retries; i++) {
        try {
          await mainWindow.loadURL("http://127.0.0.1:5173");
          return;
        } catch (err) {
          await new Promise((r) => setTimeout(r, 400));
        }
      }
      logProd("[ELECTRON] Dev server unreachable after retries, loading dist/index.html fallback...");
      mainWindow.loadFile(distPath);
    };
    loadDevServer();
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    logProd(`[PROD] loading renderer from: ${distPath}`);
    mainWindow.loadFile(distPath).catch((err) => {
      logProd(`[PROD ERROR] Failed to loadFile(${distPath}): ${err.message}`);
    });
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// Wire IPC Status Handlers
ipcMain.handle("backend:get-status", () => {
  return backendManager.getStatusState();
});

ipcMain.handle("backend:restart", async () => {
  try {
    backendManager.killBackend();
    await backendManager.start();
    return { success: true };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

ipcMain.handle("app:quit", async () => {
  console.log("[ELECTRON] Self-close IPC invoked ('Close IRIS'); closing application...");
  cleanupAndKillBackend();
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.close();
  } else {
    app.quit();
  }
  return { success: true };
});

backendManager.onStatusChange = (statusState) => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("backend:status-changed", statusState);
  }
};

function cleanupAndKillBackend() {
  try {
    backendManager.killBackend();
  } catch (e) {
    console.error("[ELECTRON] Error in cleanupAndKillBackend:", e);
  }
}

app.whenReady().then(async () => {
  try {
    await backendManager.start();
  } catch (err) {
    console.error("[ELECTRON CRITICAL] Startup failed:", err.message);
  } finally {
    createWindow();
  }
});

app.on("before-quit", () => {
  if (isQuitting) return;
  isQuitting = true;
  cleanupAndKillBackend();
});

app.on("will-quit", () => {
  cleanupAndKillBackend();
});

app.on("window-all-closed", () => {
  cleanupAndKillBackend();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

process.on("exit", () => {
  cleanupAndKillBackend();
});

process.on("SIGINT", () => {
  cleanupAndKillBackend();
  process.exit(0);
});

process.on("SIGTERM", () => {
  cleanupAndKillBackend();
  process.exit(0);
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
