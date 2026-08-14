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

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
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
    await backendManager.restart();
    return { success: true };
  } catch (err) {
    return { success: false, error: err.message };
  }
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
