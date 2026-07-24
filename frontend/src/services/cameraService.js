/**
 * Camera API service
 * All camera-related HTTP calls go through here.
 * Components never call `api` directly — they use this service or the hook.
 */
import api from "./api";

const cameraService = {
  getStatus: () => api.get("/camera/status"),
  start:     () => api.post("/camera/start"),
  stop:      () => api.post("/camera/stop"),
};

export default cameraService;
