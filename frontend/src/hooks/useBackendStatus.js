/**
 * useBackendStatus
 * Calls GET /health on mount and every `intervalMs` milliseconds.
 * Returns { online: boolean, version: string }
 */
import { useState, useEffect } from "react";
import api from "../services/api";

export function useBackendStatus(intervalMs = 5000) {
  const [state, setState] = useState({ online: false, version: null });

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const { data } = await api.get("/health");
        if (!cancelled) setState({ online: true, version: data.version });
      } catch {
        if (!cancelled) setState({ online: false, version: null });
      }
    };

    check();
    const id = setInterval(check, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  return state;
}
