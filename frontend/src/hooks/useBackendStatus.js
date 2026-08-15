/**
 * useBackendStatus
 * Calls GET /health on mount and every `intervalMs` milliseconds.
 * Returns { online: boolean, version: string }
 */
import { useState, useEffect } from "react";
import { IRISApiClient } from "../services/api_client";

export function useBackendStatus(intervalMs = 5000) {
  const [state, setState] = useState({ online: false, version: null });

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const data = await IRISApiClient.getHealth();
        if (!cancelled && data && data.status !== "OFFLINE") {
          setState({ online: true, version: data.version || "4.0.0" });
        } else if (!cancelled) {
          setState({ online: false, version: null });
        }
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
