/**
 * Voice API service.
 * All voice-related HTTP calls are defined here.
 */
import api from "./api";

const voiceService = {
  getStatus: () => api.get("/voice/status"),
  start: (mode) => api.post("/voice/start", mode ? { mode } : {}),
  stop: () => api.post("/voice/stop"),
  setMode: (mode) => api.post("/voice/mode", { mode }),
  pushToTalkStart: () => api.post("/voice/push-to-talk/start"),
  pushToTalkStop: () => api.post("/voice/push-to-talk/stop"),
};

export default voiceService;
