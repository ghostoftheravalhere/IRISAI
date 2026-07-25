/**
 * Camera API service.
 * All camera-related HTTP calls and URLs are defined here.
 */
import api from "./api";

const buildUrl = (path) => {
  const baseUrl = api.defaults.baseURL ?? "";
  return `${baseUrl.replace(/\/$/, "")}${path}`;
};

const cameraService = {
  getStatus: () => api.get("/camera/status"),
  start: () => api.post("/camera/start"),
  stop: () => api.post("/camera/stop"),
  getStreamUrl: () => buildUrl("/camera/stream"),
};

export default cameraService;
