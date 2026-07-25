/**
 * useCameraStatus
 * Loads camera status on mount and exposes manual camera actions.
 *
 * Refresh behavior is intentionally manual:
 * - on page load
 * - after Start
 * - after Stop
 * - when Refresh is clicked
 */
import { useCallback, useEffect, useState } from "react";

import cameraService from "../services/cameraService";

export function useCameraStatus() {
  const [state, setState] = useState({ connected: false, running: false });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadStatus = useCallback(async () => {
    const { data } = await cameraService.getStatus();
    setState({ connected: data.connected, running: data.running });
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      await loadStatus();
    } catch (err) {
      setState({ connected: false, running: false });
      setError(err.response?.data?.detail ?? "Failed to refresh camera status.");
    } finally {
      setLoading(false);
    }
  }, [loadStatus]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const start = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      await cameraService.start();
      await loadStatus();
    } catch (err) {
      setError(err.response?.data?.detail ?? "Failed to start camera.");
    } finally {
      setLoading(false);
    }
  }, [loadStatus]);

  const stop = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      await cameraService.stop();
      await loadStatus();
    } catch (err) {
      setError(err.response?.data?.detail ?? "Failed to stop camera.");
    } finally {
      setLoading(false);
    }
  }, [loadStatus]);

  return { ...state, loading, error, start, stop, refresh };
}
