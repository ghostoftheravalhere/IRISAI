import { useCallback, useEffect, useMemo, useState } from "react";

import calibrationService from "../services/calibrationService";
import {
  isCalibrationAuthorized,
  splitTargetsByMode,
} from "../utils/calibrationCoordinates";

const INITIAL_PROGRESS = {
  current_point: { index: 0, x: 0.1, y: 0.1 },
  completed_points: 0,
  total_points: 20,
  progress: 0,
  complete: false,
  quality: null,
  phase: "training",
  validation_report: null,
  is_calibrated: false,
};

export function useCalibrationWizard() {
  const [progress, setProgress] = useState(INITIAL_PROGRESS);
  const [backendPoints, setBackendPoints] = useState(null);
  const [started, setStarted] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [cursorEnabled, setCursorEnabled] = useState(false);
  const [error, setError] = useState(null);
  const [trackingStatus, setTrackingStatus] = useState("Inactive");
  const [loading, setLoading] = useState(true);

  // Derived target grid definitions from backend
  const { mode, trainingPoints, validationPoints, allPoints } = useMemo(
    () => splitTargetsByMode(backendPoints, progress.total_points),
    [backendPoints, progress.total_points],
  );

  const activeIndex = progress.current_point?.index ?? progress.completed_points;
  const activePoint = progress.current_point ?? allPoints[activeIndex] ?? null;

  const isValidationPhase =
    progress.phase === "validation" ||
    (mode === "16-point" && progress.completed_points >= 16 && !progress.complete);

  const isValidationFailed =
    progress.phase === "failed" ||
    (Boolean(progress.validation_report) && !progress.validation_report.passed);

  const isAuthorized = useMemo(
    () => isCalibrationAuthorized(progress, mode),
    [progress, mode],
  );

  const progressText = useMemo(() => {
    if (mode === "16-point") {
      if (progress.complete) {
        return "Complete (16 Training + 4 Validation)";
      }
      if (isValidationPhase) {
        const valIndex = Math.min(Math.max(progress.completed_points - 16, 0), 4);
        return `Validation: ${valIndex} / 4 targets`;
      }
      return `Training: ${Math.min(progress.completed_points, 16)} / 16 targets`;
    }
    // 9-point legacy mode
    return `${progress.completed_points} / ${progress.total_points}`;
  }, [mode, progress.complete, isValidationPhase, progress.completed_points, progress.total_points]);

  const progressPercent = useMemo(
    () => Math.min(Math.max(progress.progress * 100, 0), 100),
    [progress.progress],
  );

  const [guidance, setGuidance] = useState({
    status: "good",
    message: "Center your face in front of camera",
    is_stable: true,
    confidence: 1.0,
  });

  const refreshState = useCallback(async () => {
    try {
      const { data } = await calibrationService.getState();
      if (data?.points && Array.isArray(data.points) && data.points.length === 20) {
        setBackendPoints(data.points);
      } else {
        setBackendPoints(null);
      }
      return data;
    } catch {
      return null;
    }
  }, []);

  const refreshProgress = useCallback(async () => {
    try {
      const { data } = await calibrationService.getProgress();
      const is9Point = data?.mode === "9-point" || data?.total_points === 9;
      // If backend was left in 9-point legacy mode, keep the 16-point wizard initialized at 0/16
      if (is9Point) {
        setProgress(INITIAL_PROGRESS);
        setStarted(false);
      } else {
        setProgress(data);
        if (data.complete || data.phase === "complete" || data.phase === "failed") {
          setStarted(false);
        } else if (data.completed_points > 0) {
          setStarted(true);
        }
      }
      return data;
    } catch (err) {
      setTrackingStatus("Inactive");
      throw err;
    }
  }, []);

  // Initial load: fetch configuration, current state, and cursor status
  useEffect(() => {
    let mounted = true;
    Promise.all([
      refreshProgress(),
      refreshState(),
      calibrationService.getCursorStatus().catch(() => ({ data: { enabled: false } })),
    ])
      .then(([, , cursorRes]) => {
        if (!mounted) return;
        if (cursorRes?.data?.enabled !== undefined) {
          setCursorEnabled(Boolean(cursorRes.data.enabled));
        }
      })
      .catch((err) => {
        if (!mounted) return;
        const detail = err.response?.data?.detail;
        const message =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail) && detail[0]?.msg
            ? detail[0].msg
            : err.message ?? "Could not connect to eye calibration backend.";
        setError(message);
        setTrackingStatus("Inactive");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [refreshProgress, refreshState]);

  // Guidance polling when actively calibrating
  useEffect(() => {
    let interval = null;
    if (started && !progress.complete) {
      interval = setInterval(async () => {
        try {
          const { data } = await calibrationService.getGuidance();
          setGuidance(data);
        } catch {
          // Ignore transient polling errors
        }
      }, 200);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [started, progress.complete]);

  const start = useCallback(async (selectedMode = null) => {
    setError(null);
    setCursorEnabled(false);
    try {
      const modeParam = typeof selectedMode === "string" ? selectedMode : "16-point";
      const { data } = await calibrationService.restart({ mode: modeParam });
      setProgress(data);
      setStarted(true);
      setTrackingStatus("Waiting");
      await refreshState();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const message =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail) && detail[0]?.msg
          ? detail[0].msg
          : err.message ?? "Failed to start eye calibration.";
      setError(message);
      setTrackingStatus("Inactive");
    }
  }, [refreshState]);

  const cancel = useCallback(() => {
    setStarted(false);
    setError(null);
    setTrackingStatus("Inactive");
  }, []);

  const restart = useCallback(async (selectedMode = null) => {
    setError(null);
    setCursorEnabled(false);
    try {
      const modeParam = typeof selectedMode === "string" ? selectedMode : "16-point";
      const { data } = await calibrationService.restart({ mode: modeParam });
      setProgress(data);
      setStarted(true);
      setTrackingStatus("Waiting");
      await refreshState();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const message =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail) && detail[0]?.msg
          ? detail[0].msg
          : err.message ?? "Failed to restart calibration.";
      setError(message);
    }
  }, [refreshState]);

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
      if (data.complete || data.phase === "complete" || data.phase === "failed") {
        setStarted(false);
      }
    } catch (err) {
      setTrackingStatus("Retry Needed");
      const detail =
        err.response?.data?.detail ??
        err.message ??
        "Capture failed. Please stabilize your gaze and retry.";
      setError(detail);
      // Synchronize with backend without clearing started state on retry
      try {
        const { data } = await calibrationService.getProgress();
        if (data && (data.mode === "16-point" || data.total_points === 20)) {
          setProgress(data);
          if (data.complete || data.phase === "complete" || data.phase === "failed") {
            setStarted(false);
          }
        }
      } catch {
        // Ignore secondary progress fetch errors during capture retry
      }
    } finally {
      setCapturing(false);
    }
  }, [capturing, progress.complete, refreshProgress, started]);

  const finish = useCallback(() => {
    setStarted(false);
    setError(null);
    window.location.hash = "#/";
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
      const detail =
        err.response?.data?.detail ??
        "Could not enable cursor control. Ensure calibration validation gates passed.";
      setError(detail);
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
    activePoint,
    allPoints,
    capturing,
    cursorEnabled,
    error,
    guidance,
    isAuthorized,
    isValidationFailed,
    isValidationPhase,
    loading,
    mode,
    progress,
    progressPercent,
    progressText,
    started,
    trainingPoints,
    trackingPoints: trainingPoints,
    trackingStatus,
    validationPoints,
    cancel,
    captureCurrentPoint,
    disableCursor,
    enableCursor,
    finish,
    refreshProgress,
    refreshState,
    restart,
    start,
  };
}
