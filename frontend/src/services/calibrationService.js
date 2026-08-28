/**
 * Calibration API service.
 * Keeps calibration HTTP calls behind the frontend service layer.
 */
import api from "./api";

const calibrationService = {
  getProgress: () => api.get("/eye/calibration/progress"),
  restart: () => api.post("/eye/calibration/restart"),
  capture: () => api.post("/eye/calibration/capture"),
  getStatus: () => api.get("/eye/status"),
  getGuidance: () => api.get("/eye/calibration/guidance"),
  enableCursor: () => api.post("/eye/cursor/enable"),
  disableCursor: () => api.post("/eye/cursor/disable"),
  getCursorStatus: () => api.get("/api/cursor/status"),
  toggleCursor: (enabled = null) => api.post("/api/cursor/toggle", enabled !== null ? { enabled } : {}),
};

export default calibrationService;
