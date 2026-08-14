/**
 * IRIS AI V3 — REST & WebSocket Service Client
 */

const API_BASE_URL = "http://localhost:8000";
const WS_BASE_URL = "ws://localhost:8000/ws/events";

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
}

export class IRISWebSocketClient {
  constructor(onEventCallback, onStatusChangeCallback) {
    this.onEvent = onEventCallback;
    this.onStatusChange = onStatusChangeCallback;
    this.ws = null;
    this.reconnectTimer = null;
  }

  connect() {
    try {
      this.ws = new WebSocket(WS_BASE_URL);
      this.ws.onopen = () => {
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
        if (this.onStatusChange) this.onStatusChange("DISCONNECTED");
        this.scheduleReconnect();
      };
      this.ws.onerror = () => {
        if (this.onStatusChange) this.onStatusChange("ERROR");
      };
    } catch (err) {
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 3000);
    }
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) this.ws.close();
  }
}
