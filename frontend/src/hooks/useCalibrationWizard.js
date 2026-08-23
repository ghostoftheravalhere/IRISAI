import { useCallback, useEffect, useMemo, useState } from "react";

import calibrationService from "../services/calibrationService";

const INITIAL_PROGRESS = {
  current_point: { index: 0, x: 0.1, y: 0.1 },
  completed_points: 0,
  total_points: 9,
  progress: 0,
  complete: false,
  quality: null,
};

export function useCalibrationWizard() {
  const [progress, setProgress] = useState(INITIAL_PROGRESS);
  const [started, setStarted] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [cursorEnabled, setCursorEnabled] = useState(false);
  const [error, setError] = useState(null);
  const [trackingStatus, setTrackingStatus] = useState("Inactive");

  const activeIndex = progress.current_point?.index ?? progress.completed_points;
  const progressText = `${progress.completed_points} / ${progress.total_points}`;
  const progressPercent = useMemo(
    () => Math.min(Math.max(progress.progress * 100, 0), 100),
    [progress.progress],
  );

  const [guidance, setGuidance] = useState({
    status: "good",
    message: "Good position — hold steady",
    is_stable: true,
    confidence: 1.0,
  });

  const refreshProgress = useCallback(async () => {
    const { data } = await calibrationService.getProgress();
    setProgress(data);
    setStarted(data.completed_points > 0 && !data.complete);
    return data;
  }, []);

  useEffect(() => {
    refreshProgress().catch(() => {
      setTrackingStatus("Inactive");
    });
  }, [refreshProgress]);

  useEffect(() => {
    let interval = null;
    if (started && !progress.complete) {
      interval = setInterval(async () => {
        try {
          const { data } = await calibrationService.getGuidance();
          setGuidance(data);
        } catch (err) {
          // Ignore poll errors
        }
      }, 200);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [started, progress.complete]);

  const start = useCallback(async () => {
    setError(null);
    setCursorEnabled(false);
    const { data } = await calibrationService.restart();
    setProgress(data);
    setStarted(true);
    setTrackingStatus("Waiting");
  }, []);

  const cancel = useCallback(() => {
    setStarted(false);
    setError(null);
    setTrackingStatus("Inactive");
  }, []);

  const restart = useCallback(async () => {
    setError(null);
    setCursorEnabled(false);
    const { data } = await calibrationService.restart();
    setProgress(data);
    setStarted(true);
    setTrackingStatus("Waiting");
  }, []);

  const captureCurrentPoint = useCallback(async () => {
    if (!started || progress.complete || capturing) {
      return;
    }

    setCapturing(true);
    setError(null);
    setTrackingStatus("Capturing");

    try {
      const { data } = await calibrationService.capture();
      setProgress(data);
      setTrackingStatus("Active");
      if (data.complete) {
        setStarted(false);
      }
    } catch (err) {
      setTrackingStatus("Inactive");
      setError(err.response?.data?.detail ?? "Could not capture the current point.");
    } finally {
      setCapturing(false);
    }
  }, [capturing, progress.complete, started]);

  const finish = useCallback(() => {
    setStarted(false);
    setError(null);
  }, []);

  const enableCursor = useCallback(async () => {
    setError(null);

    try {
      const { data } = await calibrationService.enableCursor();
      setCursorEnabled(Boolean(data.enabled));
      if (!data.enabled) {
        setError("Cursor control could not be enabled on this system.");
      }
    } catch (err) {
      setError(err.response?.data?.detail ?? "Could not enable cursor control.");
    }
  }, []);

  const disableCursor = useCallback(async () => {
    setError(null);

    try {
      const { data } = await calibrationService.disableCursor();
      setCursorEnabled(Boolean(data.enabled));
    } catch (err) {
      setError(err.response?.data?.detail ?? "Could not disable cursor control.");
    }
  }, []);

  return {
    activeIndex,
    capturing,
    cursorEnabled,
    error,
    guidance,
    progress,
    progressPercent,
    progressText,
    started,
    trackingStatus,
    cancel,
    captureCurrentPoint,
    disableCursor,
    enableCursor,
    finish,
    refreshProgress,
    restart,
    start,
  };
}
