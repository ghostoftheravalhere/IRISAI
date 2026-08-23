import config from "../config.js";

const API_BASE_URL = config.API_BASE_URL;
const WS_BASE_URL = config.WS_BASE_URL;

export class IRISApiClient {
  static async getHealth() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/health`);
      return await res.json();
    } catch (e) {
      return { status: "OFFLINE", error: e.message };
    }
  }

  static async getMetrics() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/metrics`);
      return await res.json();
    } catch (e) {
      return { counters: {}, gauges: {}, latency_ms: {} };
    }
  }

  static async getSkills() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/skills`);
      return await res.json();
    } catch (e) {
      return { skills: [] };
    }
  }

  static async executeCommand(commandText) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: commandText }),
      });
      return await res.json();
    } catch (e) {
      return { success: false, error: e.message };
    }
  }

  static async getWorldSnapshot() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/context/snapshot`);
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  static async speak(text) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/voice/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      return await res.json();
    } catch (e) {
      return { success: false, error: e.message };
    }
  }

  static async startVoice(mode = "continuous") {
    try {
      const res = await fetch(`${API_BASE_URL}/voice/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      return await res.json();
    } catch (e) {
      return { microphoneStatus: "Error", error: e.message };
    }
  }

  static async stopVoice() {
    try {
      const res = await fetch(`${API_BASE_URL}/voice/stop`, { method: "POST" });
      return await res.json();
    } catch (e) {
      return { microphoneStatus: "Off", error: e.message };
    }
  }

  static async getVoiceDiagnostics() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/voice/diagnostics`);
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  static async retryVoice() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/voice/retry`, { method: "POST" });
      return await res.json();
    } catch (e) {
      return { microphoneStatus: "Error", error: e.message };
    }
  }

  static async getVoiceStatus() {
    try {
      const res = await fetch(`${API_BASE_URL}/voice/status`);
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  static async startCamera() {
    try {
      const res = await fetch(`${API_BASE_URL}/camera/start`, { method: "POST" });
      return await res.json();
    } catch (e) {
      return { connected: false, running: false, error: e.message };
    }
  }

  static async stopCamera() {
    try {
      const res = await fetch(`${API_BASE_URL}/camera/stop`, { method: "POST" });
      return await res.json();
    } catch (e) {
      return { connected: false, running: false, error: e.message };
    }
  }

  static async getCameraStatus() {
    try {
      const res = await fetch(`${API_BASE_URL}/camera/status`);
      return await res.json();
    } catch (e) {
      return { connected: false, running: false };
    }
  }

  static async getDiagnostics() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/diagnostics`);
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  static async getEyeStatus() {
    try {
      const res = await fetch(`${API_BASE_URL}/eye/status`);
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  static async restartCalibration() {
    try {
      const res = await fetch(`${API_BASE_URL}/eye/calibration/restart`, { method: "POST" });
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  static async captureCalibrationPoint() {
    try {
      const res = await fetch(`${API_BASE_URL}/eye/calibration/capture`, { method: "POST" });
      return await res.json();
    } catch (e) {
      return { error: e.message };
    }
  }

  static async enableCursor() {
    try {
      const res = await fetch(`${API_BASE_URL}/eye/cursor/enable`, { method: "POST" });
      return await res.json();
    } catch (e) {
      return { enabled: false, error: e.message };
    }
  }

  static async disableCursor() {
    try {
      const res = await fetch(`${API_BASE_URL}/eye/cursor/disable`, { method: "POST" });
      return await res.json();
    } catch (e) {
      return { enabled: false, error: e.message };
    }
  }

  static async getGoogleStatus() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/google/status`);
      return await res.json();
    } catch (e) {
      return { is_connected: false };
    }
  }

  static async getGitHubStatus() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/github/status`);
      return await res.json();
    } catch (e) {
      return { is_connected: false };
    }
  }

  static async getEventHistory() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/events/history`);
      return await res.json();
    } catch (e) {
      return { events: [] };
    }
  }

  static async getInstalledApps() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/apps`);
      return await res.json();
    } catch (e) {
      return { applications: [] };
    }
  }
}

export class IRISWebSocketClient {
  constructor(onEventCallback, onStatusChangeCallback) {
    this.onEvent = onEventCallback;
    this.onStatusChange = onStatusChangeCallback;
    this.ws = null;
    this.reconnectTimer = null;
    this.isConnecting = false;
  }

  connect() {
    if (this.isConnecting) return;
    this.isConnecting = true;
    try {
      if (this.ws) {
        try {
          this.ws.close();
        } catch (e) {}
      }
      this.ws = new WebSocket(WS_BASE_URL);
      this.ws.onopen = () => {
        this.isConnecting = false;
        if (this.onStatusChange) this.onStatusChange("CONNECTED");
      };
      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (this.onEvent) this.onEvent(data);
        } catch (err) {
          console.error("WebSocket message parse error", err);
        }
      };
      this.ws.onclose = () => {
        this.isConnecting = false;
        if (this.onStatusChange) this.onStatusChange("DISCONNECTED");
        this.scheduleReconnect();
      };
      this.ws.onerror = () => {
        this.isConnecting = false;
        if (this.onStatusChange) this.onStatusChange("ERROR");
        this.scheduleReconnect();
      };
    } catch (err) {
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 2000);
    }
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) {
      try {
        this.ws.close();
      } catch (e) {}
    }
  }
}
