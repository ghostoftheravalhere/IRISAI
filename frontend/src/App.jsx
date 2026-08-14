import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Camera from "./pages/Camera";
import Calibration from "./pages/Calibration";
import Voice from "./pages/Voice";
import api from "./services/api";

export default function App() {
  const [backendState, setBackendState] = useState({
    status: "connecting",
    message: "Connecting to IRIS AI Backend...",
  });
  const [restarting, setRestarting] = useState(false);

  useEffect(() => {
    // 1. Electron Environment Check
    if (window.irisAPI && typeof window.irisAPI.getBackendStatus === "function") {
      window.irisAPI.getBackendStatus().then((state) => {
        if (state) setBackendState(state);
      });

      const cleanup = window.irisAPI.onBackendStatusChange((state) => {
        if (state) {
          setBackendState(state);
          if (state.status === "ready") {
            setRestarting(false);
          }
        }
      });

      return () => {
        if (cleanup) cleanup();
      };
    }

    // 2. Fallback Web Browser HTTP Check (Non-Electron)
    let isMounted = true;
    const checkWebHealth = async () => {
      try {
        const { data } = await api.get("/health");
        if (isMounted && data && (data.status === "online" || data.status === "ok")) {
          setBackendState({
            status: "ready",
            message: "Backend connected",
          });
        }
      } catch (e) {
        if (isMounted) {
          setBackendState({
            status: "error",
            message: "IRIS Backend unreachable at http://127.0.0.1:8000",
          });
        }
      }
    };

    checkWebHealth();
    const interval = setInterval(checkWebHealth, 3000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleRestart = async () => {
    setRestarting(true);
    setBackendState({
      status: "restarting",
      message: "Restarting Python backend process...",
    });

    if (window.irisAPI && typeof window.irisAPI.restartBackend === "function") {
      try {
        const res = await window.irisAPI.restartBackend();
        if (!res.success) {
          setBackendState({
            status: "error",
            message: res.error || "Failed to restart backend",
          });
          setRestarting(false);
        }
      } catch (err) {
        setBackendState({
          status: "error",
          message: err.message || "Failed to restart backend",
        });
        setRestarting(false);
      }
    } else {
      // Non-Electron browser retry
      try {
        const { data } = await api.get("/health");
        if (data && (data.status === "online" || data.status === "ok")) {
          setBackendState({ status: "ready", message: "Backend connected" });
        } else {
          setBackendState({ status: "error", message: "Backend returned non-ok health status" });
        }
      } catch (err) {
        setBackendState({ status: "error", message: "Backend still unreachable" });
      } finally {
        setRestarting(false);
      }
    }
  };

  const isReady = backendState.status === "ready";
  const isLoading =
    backendState.status === "starting" ||
    backendState.status === "connecting" ||
    backendState.status === "restarting";

  if (!isReady) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          backgroundColor: "#0a0a0f",
          color: "#f3f4f6",
          fontFamily: "system-ui, -apple-system, sans-serif",
          padding: "2rem",
          textAlign: "center",
        }}
      >
        <div
          style={{
            background: "#12131c",
            border: "1px solid #27273a",
            borderRadius: "16px",
            padding: "2.5rem 3rem",
            maxWidth: "480px",
            width: "100%",
            boxShadow: "0 20px 40px rgba(0,0,0,0.5)",
          }}
        >
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "50%",
              border: isLoading ? "3px solid #3b82f6" : "3px solid #ef4444",
              borderTopColor: isLoading ? "transparent" : "#ef4444",
              animation: isLoading ? "spin 1s linear infinite" : "none",
              margin: "0 auto 1.5rem auto",
            }}
          />
          <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>

          <h2 style={{ fontSize: "1.35rem", fontWeight: "600", marginBottom: "0.5rem" }}>
            {isLoading ? "Starting IRIS AI" : "Backend Unavailable"}
          </h2>

          <p style={{ color: "#9ca3af", fontSize: "0.95rem", lineHeight: "1.5", marginBottom: "1.75rem" }}>
            {backendState.message || "Waiting for backend services to initialize..."}
          </p>

          {!isLoading && (
            <button
              onClick={handleRestart}
              disabled={restarting}
              style={{
                backgroundColor: restarting ? "#374151" : "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                padding: "0.75rem 1.75rem",
                fontSize: "0.95rem",
                fontWeight: "500",
                cursor: restarting ? "not-allowed" : "pointer",
                transition: "background-color 0.2s ease",
              }}
            >
              {restarting ? "Restarting..." : "Restart Backend"}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/camera" element={<Camera />} />
        <Route path="/calibration" element={<Calibration />} />
        <Route path="/voice" element={<Voice />} />
      </Routes>
    </BrowserRouter>
  );
}
