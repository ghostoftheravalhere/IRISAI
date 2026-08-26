import config from "../config.js";

const API_BASE_URL = config.API_BASE_URL;
const WS_BASE_URL = config.WS_BASE_URL;

async function safeFetchJson(url, options = {}) {
  try {
    const res = await fetch(url, options);
    const contentType = res.headers.get("content-type") || "";
    let data = null;
    if (contentType.includes("application/json")) {
      try {
        data = await res.json();
      } catch {
        data = null;
      }
    } else {
      const text = await res.text().catch(() => "");
      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = null;
        }
      }
    }

    if (!res.ok) {
      const errorMsg =
        (data && (data.detail || data.error || data.message)) ||
        `HTTP ${res.status}`;
      return { ok: false, status: res.status, data, error: errorMsg };
    }
    return { ok: true, status: res.status, data: data ?? {} };
  } catch (e) {
    return { ok: false, status: 0, error: e.message || "Network request failed" };
  }
}

export class IRISApiClient {
  static async getHealth() {
    const res = await safeFetchJson(`${API_BASE_URL}/api/v1/health`);
    return res.ok ? res.data : { status: "OFFLINE", error: res.error };
  }

  static async getMetrics() {
    const res = await safeFetchJson(`${API_BASE_URL}/api/v1/metrics`);
    return res.ok ? res.data : { counters: {}, gauges: {}, latency_ms: {} };
  }

  static async getSkills() {
    const res = await safeFetchJson(`${API_BASE_URL}/api/v1/skills`);
    return res.ok ? res.data : { skills: [] };
  }

  static async executeCommand(commandText) {
    const res = await safeFetchJson(`${API_BASE_URL}/api/v1/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: commandText }),
    });
    return res.ok ? res.data : { success: false, error: res.error };
  }

  static async getWorldSnapshot() {
    const res = await safeFetchJson(`${API_BASE_URL}/api/v1/context/snapshot`);
    return res.ok ? res.data : null;
  }

  static async speak(text) {
    const res = await safeFetchJson(`${API_BASE_URL}/api/v1/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    return res.ok ? res.data : { success: false, error: res.error };
  }

  static async startVoice(mode = "continuous") {
    const res = await safeFetchJson(`${API_BASE_URL}/voice/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    return res.ok ? res.data : { microphoneStatus: "Error", error: res.error };
  }

  static async stopVoice() {
    const res = await safeFetchJson(`${API_BASE_URL}/voice/stop`, { method: "POST" });
    return res.ok ? res.data : { microphoneStatus: "Off", error: res.error };
  }

  static async getVoiceDiagnostics() {
    const res = await safeFetchJson(`${API_BASE_URL}/api/v1/voice/diagnostics`);
    return res.ok ? res.data : null;
  }

  static async retryVoice() {
    const res = await safeFetchJson(`${API_BASE_URL}/api/v1/voice/retry`, { method: "POST" });
    return res.ok ? res.data : { microphoneStatus: "Error", error: res.error };
  }

  static async getVoiceStatus() {
    const res = await safeFetchJson(`${API_BASE_URL}/voice/status`);
    return res.ok ? res.data : null;
  }

  static async startCamera() {
    const res = await safeFetchJson(`${API_BASE_URL}/camera/start`, { method: "POST" });
    return res.ok ? res.data : { connected: false, running: false, error: res.error };
  }

  static async stopCamera() {
    const res = await safeFetchJson(`${API_BASE_URL}/camera/stop`, { method: "POST" });
    return res.ok ? res.data : { connected: false, running: false, error: res.error };
  }

  static async getCameraStatus() {
    const res = await safeFetchJson(`${API_BASE_URL}/camera/status`);
    return res.ok ? res.data : { connected: false, running: false };
  }

  static async getDiagnostics() {
    const res = await safeFetchJson(`${API_BASE_URL}/api/v1/diagnostics`);
    return res.ok ? res.data : null;
  }

  static async getEyeStatus() {
    const res = await safeFetchJson(`${API_BASE_URL}/eye/status`);
    return res.ok ? res.data : null;
  }

  static async restartCalibration() {
    const res = await safeFetchJson(`${API_BASE_URL}/eye/calibration/restart`, { method: "POST" });
    return res.ok ? res.data : { error: res.error };
  }

  static async captureCalibrationPoint() {
    const res = await safeFetchJson(`${API_BASE_URL}/eye/calibration/capture`, { method: "POST" });
    return res.ok ? res.data : { error: res.error };
  }

  static async enableCursor() {
    const res = await safeFetchJson(`${API_BASE_URL}/eye/cursor/enable`, { method: "POST" });
    if (!res.ok) {
      return { enabled: false, error: res.error };
    }
    return res.data;
  }

  static async disableCursor() {
    const res = await safeFetchJson(`${API_BASE_URL}/eye/cursor/disable`, { method: "POST" });
    if (!res.ok) {
      return { enabled: false, error: res.error };
    }
    return res.data;
  }

  static async getGoogleStatus() {
    const res = await safeFetchJson(`${API_BASE_URL}/api/auth/google/status`);
    return res.ok ? res.data : { is_connected: false };
  }

  static async getGitHubStatus() {
    const res = await safeFetchJson(`${API_BASE_URL}/api/auth/github/status`);
    return res.ok ? res.data : { is_connected: false };
  }

  static async getEventHistory() {
    const res = await safeFetchJson(`${API_BASE_URL}/api/v1/events/history`);
    return res.ok ? res.data : { events: [] };
  }

  static async getInstalledApps() {
    const res = await safeFetchJson(`${API_BASE_URL}/api/v1/apps`);
    return res.ok ? res.data : { applications: [] };
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
