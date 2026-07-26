/**
 * useVoiceStatus
 * Polls voice recognition status and exposes start/stop/mode controls.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import voiceService from "../services/voiceService";

const EMPTY_STATE = {
  microphoneStatus: "Off",
  listening: false,
  listenMode: "continuous",
  pushToTalkActive: false,
  latestTranscript: null,
  detectedIntent: null,
  executionStatus: "Idle",
  error: null,
};

export function useVoiceStatus({ pollMs = 750 } = {}) {
  const [state, setState] = useState(EMPTY_STATE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const mounted = useRef(true);

  const applyState = useCallback((data) => {
    if (!mounted.current) return;
    setState({
      microphoneStatus: data.microphoneStatus ?? "Off",
      listening: Boolean(data.listening),
      listenMode: data.listenMode ?? "continuous",
      pushToTalkActive: Boolean(data.pushToTalkActive),
      latestTranscript: data.latestTranscript ?? null,
      detectedIntent: data.detectedIntent ?? null,
      executionStatus: data.executionStatus ?? "Idle",
      error: data.error ?? null,
    });
  }, []);

  const loadStatus = useCallback(async () => {
    const { data } = await voiceService.getStatus();
    applyState(data);
    return data;
  }, [applyState]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await loadStatus();
    } catch (err) {
      applyState(EMPTY_STATE);
      setError(err.response?.data?.detail ?? "Failed to refresh voice status.");
    } finally {
      setLoading(false);
    }
  }, [applyState, loadStatus]);

  useEffect(() => {
    mounted.current = true;
    refresh();
    const timer = setInterval(() => {
      loadStatus().catch(() => {
        /* keep last known state while offline */
      });
    }, pollMs);
    return () => {
      mounted.current = false;
      clearInterval(timer);
    };
  }, [loadStatus, pollMs, refresh]);

  const start = useCallback(
    async (mode) => {
      setLoading(true);
      setError(null);
      try {
        const { data } = await voiceService.start(mode);
        applyState(data);
      } catch (err) {
        setError(err.response?.data?.detail ?? "Failed to start voice recognition.");
      } finally {
        setLoading(false);
      }
    },
    [applyState],
  );

  const stop = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await voiceService.stop();
      applyState(data);
    } catch (err) {
      setError(err.response?.data?.detail ?? "Failed to stop voice recognition.");
    } finally {
      setLoading(false);
    }
  }, [applyState]);

  const setMode = useCallback(
    async (mode) => {
      setLoading(true);
      setError(null);
      try {
        const { data } = await voiceService.setMode(mode);
        applyState(data);
      } catch (err) {
        setError(err.response?.data?.detail ?? "Failed to change listen mode.");
      } finally {
        setLoading(false);
      }
    },
    [applyState],
  );

  const pushToTalkStart = useCallback(async () => {
    setError(null);
    try {
      const { data } = await voiceService.pushToTalkStart();
      applyState(data);
    } catch (err) {
      setError(err.response?.data?.detail ?? "Failed to start push-to-talk.");
    }
  }, [applyState]);

  const pushToTalkStop = useCallback(async () => {
    setError(null);
    try {
      const { data } = await voiceService.pushToTalkStop();
      applyState(data);
    } catch (err) {
      setError(err.response?.data?.detail ?? "Failed to stop push-to-talk.");
    }
  }, [applyState]);

  return {
    ...state,
    loading,
    error: error || state.error,
    start,
    stop,
    setMode,
    pushToTalkStart,
    pushToTalkStop,
    refresh,
  };
}
