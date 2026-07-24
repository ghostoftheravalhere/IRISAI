/**
 * useBackendStatus hook
 * Polls /api/status to check if the Python backend is reachable.
 * Usage: const { online } = useBackendStatus();
 */
import { useState, useEffect } from "react";
import api from "../services/api";

export function useBackendStatus(intervalMs = 5000) {
  const [online, setOnline] = useState(false);

  useEffect(() => {
    const check = async () => {
      try {
        await api.get("/status");
        setOnline(true);
      } catch {
        setOnline(false);
      }
    };
    check();
    const id = setInterval(check, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return { online };
}
