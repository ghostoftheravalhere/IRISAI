/**
 * Electron Preload Script
 * Safely exposes selected Electron APIs to the renderer via contextBridge.
 * Add only what the renderer strictly needs — never expose full ipcRenderer.
 */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("irisAPI", {
  platform: process.platform,
  getBackendStatus: () => ipcRenderer.invoke("backend:get-status"),
  restartBackend: () => ipcRenderer.invoke("backend:restart"),
  onBackendStatusChange: (callback) => {
    const listener = (event, statusState) => {
      if (typeof callback === "function") {
        callback(statusState);
      }
    };
    ipcRenderer.on("backend:status-changed", listener);
    return () => {
      ipcRenderer.removeListener("backend:status-changed", listener);
    };
  },
});
