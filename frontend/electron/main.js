/**
 * Electron Main Process
 * - Creates BrowserWindow
 * - Dev: loads Vite dev server + opens DevTools
 * - Prod: loads built dist/index.html
 * - Manages Python backend lifecycle via BackendManager & exposes IPC handlers
 */
const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const BackendManager = require("./backendManager");

const isDev = !app.isPackaged;
const backendManager = new BackendManager();
let mainWindow = null;
let isQuitting = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: "#0a0a0f",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Remove default menu bar
  mainWindow.setMenuBarVisibility(false);

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
      console.log("[ELECTRON] Dev server unreachable after retries, loading dist/index.html fallback...");
      mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
    };
    loadDevServer();
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  mainWindow.webContents.on("did-fail-load", (event, errorCode, errorDescription, validatedURL) => {
    console.error(`[ELECTRON RENDERER FAIL] ${errorCode}: ${errorDescription} (${validatedURL})`);
    if (validatedURL.includes("5173")) {
      console.log("[ELECTRON] Dev server load failed, loading dist/index.html fallback...");
      mainWindow.loadFile(path.join(__dirname, "../dist/index.html")).catch(() => {
        const errorHtml = `
          <html><body style="background:#0a0a0f;color:#ef4444;font-family:sans-serif;padding:3rem;text-align:center;">
            <h2>IRIS AI — Interface Load Error</h2>
            <p style="color:#9ca3af;">Frontend dev server and dist bundle unavailable. Run: npm run dev</p>
            <button onclick="location.reload()" style="background:#2563eb;color:#fff;border:none;padding:0.6rem 1.2rem;border-radius:6px;cursor:pointer;margin-top:1rem;">Retry Load</button>
          </body></html>
        `;
        mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(errorHtml)}`);
      });
    }
  });

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
    await backendManager.restart();
    return { success: true };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

ipcMain.handle("app:quit", async () => {
  console.log("[ELECTRON] Self-close IPC invoked ('Close IRIS'); closing application gracefully...");
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

app.whenReady().then(async () => {
  try {
    await backendManager.start();
  } catch (err) {
    console.error("[ELECTRON CRITICAL] Startup failed:", err.message);
  } finally {
    createWindow();
  }
});

app.on("before-quit", async (event) => {
  if (isQuitting) return;

  if (backendManager.ownedByElectron && backendManager.childProcess) {
    event.preventDefault();
    isQuitting = true;
    try {
      await backendManager.stop();
    } catch (err) {
      console.error("[ELECTRON] Error stopping backend:", err);
    } finally {
      app.quit();
    }
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
