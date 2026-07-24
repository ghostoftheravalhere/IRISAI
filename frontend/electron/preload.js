/**
 * Electron Preload Script
 * Safely exposes selected Electron APIs to the renderer via contextBridge.
 * Add only what the renderer strictly needs — never expose full ipcRenderer.
 */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("irisAPI", {
  // Placeholder — expose IPC channels as features are built
  // send: (channel, data) => ipcRenderer.send(channel, data),
  // invoke: (channel, data) => ipcRenderer.invoke(channel, data),
  platform: process.platform,
});
