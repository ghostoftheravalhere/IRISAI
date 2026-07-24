/**
 * useCameraStatus
 * Polls GET /camera/status every `intervalMs` milliseconds.
 * Also exposes start() and stop() actions that refresh state on completion.
 *
 * Returns:
 *   connected  — physical camera device is present
 *   running    — OpenCV capture session is active
 *   loading    — an action (start/stop) is in progress
 *   error      — last error message, null if none
 *   start()    — call POST /camera/start
 *   stop()     — call POST /camera/stop
 *   refresh()  — manually re-poll status
 */
import { useState, useEffect, useCallback } from "react";
import cameraService from "../services/cameraService";

export function useCameraStatus(intervalMs = 5000) {
  const [state, setState] = useState({ connected: false, running: false });
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState(null);

  const refresh = useCallback(async () => {
    try {
      const { data } = await cameraService.getStatus();
      setState({ connected: data.connected, running: data.running });
      setError(null);
    } catch {
      setState({ connected: false, running: false });
    }
  }, []);

  // Poll on mount and on interval
  useEffect(() => {
    let cancelled = false;
    const poll = async () => { if (!cancelled) await refresh(); };
    poll();
    const id = setInterval(poll, intervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [refresh, intervalMs]);

  const start = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await cameraService.start();
      await refresh();
    } catch (err) {
      setError(err.response?.data?.detail ?? "Failed to start camera.");
    } finally {
      setLoading(false);
    }
  }, [refresh]);

  const stop = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await cameraService.stop();
      await refresh();
    } catch (err) {
      setError(err.response?.data?.detail ?? "Failed to stop camera.");
    } finally {
      setLoading(false);
    }
  }, [refresh]);

  return { ...state, loading, error, start, stop, refresh };
}
