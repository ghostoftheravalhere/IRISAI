/**
 * Calibration API service.
 * Keeps calibration HTTP calls behind the frontend service layer.
 */
import api from "./api";

const calibrationService = {
  getProgress: () => api.get("/eye/calibration/progress"),
  getState: () => api.get("/eye/calibration/state"),
  getMapping: () => api.get("/eye/calibration/mapping"),
  restart: (mode = null) => {
    let modeStr = null;
    if (typeof mode === "string") {
      modeStr = mode.trim();
    } else if (mode && typeof mode === "object" && typeof mode.mode === "string") {
      modeStr = mode.mode.trim();
    }
    const payload = modeStr ? { mode: modeStr } : {};
    return api.post("/eye/calibration/restart", payload);
  },
  capture: () => api.post("/eye/calibration/capture"),
  getStatus: () => api.get("/eye/status"),
  getGuidance: () => api.get("/eye/calibration/guidance"),
  enableCursor: () => api.post("/eye/cursor/enable"),
  disableCursor: () => api.post("/eye/cursor/disable"),
  getCursorStatus: () => api.get("/api/cursor/status"),
  toggleCursor: (enabled = null) => api.post("/api/cursor/toggle", enabled !== null ? { enabled } : {}),
  recalibrateCenter: (neutral_x = null, neutral_y = null) => {
    const payload = neutral_x !== null && neutral_y !== null ? { neutral_x, neutral_y } : {};
    return api.post("/eye/recalibrate-center", payload);
  },
};

export default calibrationService;
