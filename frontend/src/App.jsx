import { useEffect, useState } from "react";
import { HashRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Camera from "./pages/Camera";
import Calibration from "./pages/Calibration";
import Voice from "./pages/Voice";
import { IRISApiClient } from "./services/api_client";

export default function App() {
  const [backendState, setBackendState] = useState({
    status: "connecting",
    message: "Connecting to IRIS AI Backend...",
  });

  useEffect(() => {
    let isMounted = true;

    // 0. Apply Saved Theme
    try {
      const savedTheme = localStorage.getItem("iris_theme") || "dark";
      document.documentElement.className = "theme-" + savedTheme;
    } catch (e) {}

    // 1. Electron IPC Listener
    if (window.irisAPI && typeof window.irisAPI.getBackendStatus === "function") {
      window.irisAPI.getBackendStatus().then((state) => {
        if (isMounted && state) setBackendState(state);
      });

      window.irisAPI.onBackendStatusChange((state) => {
        if (isMounted && state) {
          setBackendState(state);
        }
      });
    }

    // 2. Direct Asynchronous HTTP Health Check
    const checkDirectHealth = async () => {
      try {
        const data = await IRISApiClient.getHealth();
        if (isMounted && data && data.status !== "OFFLINE") {
          setBackendState({
            status: "ready",
            message: "Backend connected",
          });
        }
      } catch (e) {
        if (isMounted && !window.irisAPI) {
          setBackendState({
            status: "offline",
            message: "Backend unreachable at 127.0.0.1:8000",
          });
        }
      }
    };

    checkDirectHealth();
    const interval = setInterval(checkDirectHealth, 2500);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleRetry = async () => {
    if (window.irisAPI && (typeof window.irisAPI.startBackend === "function" || typeof window.irisAPI.restartBackend === "function")) {
      setBackendState({
        status: "starting",
        message: "Re-spawning backend process (surviving Defender scan)...",
      });
      try {
        const startFn = window.irisAPI.startBackend || window.irisAPI.restartBackend;
        const res = await startFn();
        if (!res?.success && res?.error) {
          setBackendState({
            status: "error",
            message: `Launch failed: ${res.error}`,
          });
        }
      } catch (e) {
        console.error("[FRONTEND] Failed to restart backend:", e);
      }
    } else {
      setBackendState({
        status: "connecting",
        message: "Re-checking local backend gateway...",
      });
      IRISApiClient.getHealth();
    }
  };

  return (
    <HashRouter>
      {backendState.status !== "ready" && (
        <div
          style={{
            background: "#1e1b4b",
            color: "#a5b4fc",
            padding: "0.4rem 1rem",
            fontSize: "0.85rem",
            textAlign: "center",
            borderBottom: "1px solid #3730a3",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.75rem",
          }}
        >
          <span>⚡ Backend Status: {backendState.status.toUpperCase()} ({backendState.message})</span>
          <button
            onClick={handleRetry}
            style={{
              background: "#312e81",
              border: "none",
              color: "#e0e7ff",
              borderRadius: "4px",
              padding: "0.2rem 0.6rem",
              fontSize: "0.75rem",
              cursor: "pointer",
            }}
          >
            ⚡ Retry Backend Launch
          </button>
        </div>
      )}

      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/camera" element={<Camera />} />
        <Route path="/calibration" element={<Calibration />} />
        <Route path="/voice" element={<Voice />} />
      </Routes>
    </HashRouter>
  );
}
