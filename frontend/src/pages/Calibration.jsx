import { useMemo, useEffect, useState, useRef, useCallback } from "react";
import { useCalibrationWizard } from "../hooks/useCalibrationWizard";
import {
  getPointQuadrant,
  getTargetPosition,
  clampPanelPosition,
  getDefaultPanelPosition,
} from "../utils/calibrationCoordinates";
import styles from "./Calibration.module.css";

export default function Calibration() {
  const {
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
    started,
    trainingPoints,
    trackingStatus,
    validationPoints,
    cancel,
    captureCurrentPoint,
    disableCursor,
    enableCursor,
    finish,
    restart,
    start,
  } = useCalibrationWizard();

  const complete = progress.complete;
  const quality = progress.quality;
  const valReport = progress.validation_report;

  const guidanceMessage = guidance?.message ?? "Center your face in front of camera";
  const isGuidanceGood = guidance?.status === "good" && guidance?.is_stable;

  // Toggle for expanded validation breakdown in floating panel
  const [showValDetails, setShowValDetails] = useState(false);

  // Electron Fullscreen Lifecycle (Request on mount, restore on unmount/exit)
  const fullscreenRequestedRef = useRef(false);
  useEffect(() => {
    if (window.irisAPI?.setFullScreen && !fullscreenRequestedRef.current) {
      fullscreenRequestedRef.current = true;
      window.irisAPI.setFullScreen(true).catch((e) => {
        console.warn("[CALIBRATION] Could not set fullscreen:", e);
      });
    }

    return () => {
      if (window.irisAPI?.setFullScreen && fullscreenRequestedRef.current) {
        fullscreenRequestedRef.current = false;
        window.irisAPI.setFullScreen(false).catch((e) => {
          console.warn("[CALIBRATION] Could not restore non-fullscreen:", e);
        });
      }
    };
  }, []);

  // Draggable Floating Panel State & Handlers
  const [panelPos, setPanelPos] = useState(null); // { x, y }
  const [isDragging, setIsDragging] = useState(false);
  const dragOffsetRef = useRef({ x: 0, y: 0 });
  const panelRef = useRef(null);

  // Compute non-colliding default docking location when panel has not been manually dragged
  const defaultPos = useMemo(() => {
    const vWidth = typeof window !== "undefined" ? window.innerWidth : 1920;
    const vHeight = typeof window !== "undefined" ? window.innerHeight : 1080;
    return getDefaultPanelPosition(
      activePoint,
      { width: 360, height: 260 },
      { width: vWidth, height: vHeight },
      24
    );
  }, [activePoint]);

  const handleDragMouseDown = useCallback((e) => {
    if (e.button !== 0) return; // Only primary mouse button
    if (e.target.tagName === "BUTTON" || e.target.closest("button") || e.target.tagName === "INPUT") {
      return;
    }

    const panelEl = panelRef.current;
    if (panelEl) {
      const rect = panelEl.getBoundingClientRect();
      dragOffsetRef.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      };
      setPanelPos({ x: rect.left, y: rect.top });
      setIsDragging(true);
    }
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e) => {
      const panelEl = panelRef.current;
      const width = panelEl?.offsetWidth || 360;
      const height = panelEl?.offsetHeight || 260;
      const vWidth = window.innerWidth;
      const vHeight = window.innerHeight;

      const clamped = clampPanelPosition(
        { x: e.clientX - dragOffsetRef.current.x, y: e.clientY - dragOffsetRef.current.y },
        { width, height },
        { width: vWidth, height: vHeight },
        12
      );
      setPanelPos(clamped);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging]);

  // Re-clamp panel position on window resize to prevent off-screen coordinates
  useEffect(() => {
    const handleResize = () => {
      setPanelPos((prev) => {
        if (!prev) return null;
        const panelEl = panelRef.current;
        const width = panelEl?.offsetWidth || 360;
        const height = panelEl?.offsetHeight || 260;
        return clampPanelPosition(
          prev,
          { width, height },
          { width: window.innerWidth, height: window.innerHeight },
          12
        );
      });
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Keyboard controls: ENTER to capture/start/restart, ESC to cancel/return
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

      if (e.key === "Enter") {
        e.preventDefault();
        if (started && !complete && !isValidationFailed && !capturing) {
          captureCurrentPoint();
        } else if (isValidationFailed) {
          restart("16-point");
        } else if (!started && !complete && !loading) {
          start("16-point");
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        if (started && !complete) {
          cancel();
        } else {
          window.location.hash = "#/";
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [started, complete, capturing, isValidationFailed, loading, captureCurrentPoint, restart, start, cancel]);

  // Phase metadata for badge
  const phaseInfo = useMemo(() => {
    if (complete) {
      return isAuthorized
        ? { text: "Complete", bg: "rgba(16, 185, 129, 0.2)", color: "#34d399" }
        : { text: "Failed", bg: "rgba(239, 68, 68, 0.2)", color: "#f87171" };
    }
    if (isValidationFailed) {
      return { text: "Failed", bg: "rgba(239, 68, 68, 0.2)", color: "#f87171" };
    }
    if (isValidationPhase) {
      return { text: "Validation", bg: "rgba(6, 182, 212, 0.2)", color: "#67e8f9" };
    }
    if (started) {
      return { text: "Training", bg: "rgba(59, 130, 246, 0.2)", color: "#93c5fd" };
    }
    return { text: "Ready", bg: "rgba(100, 116, 139, 0.25)", color: "#94a3b8" };
  }, [complete, isAuthorized, isValidationFailed, isValidationPhase, started]);

  // Active target label
  const activeTargetDescription = useMemo(() => {
    if (complete) {
      return isAuthorized ? "Complete & Authorized" : "Complete (Unauthorized)";
    }
    if (isValidationFailed) {
      return "Validation Failed";
    }
    if (!started || !activePoint) {
      return "Ready to Calibrate";
    }
    const quadrant = getPointQuadrant(activePoint.x, activePoint.y);
    if (isValidationPhase) {
      const valIdx = activeIndex >= 16 ? activeIndex - 15 : 1;
      return `Validation ${valIdx} of 4 (${quadrant})`;
    }
    const trainIdx = activeIndex + 1;
    const trainTotal = mode === "16-point" ? 16 : 9;
    return `Target ${trainIdx} of ${trainTotal} (${quadrant})`;
  }, [complete, isAuthorized, started, activePoint, isValidationPhase, activeIndex, mode]);

  // Progress text
  const stepText = useMemo(() => {
    if (mode === "16-point") {
      if (complete) return "20 / 20";
      if (isValidationPhase) {
        const valIdx = Math.min(Math.max(progress.completed_points - 16, 0), 4);
        return `Val ${valIdx} / 4`;
      }
      return `${Math.min(progress.completed_points, 16)} / 16`;
    }
    return `${progress.completed_points} / ${progress.total_points}`;
  }, [mode, complete, isValidationPhase, progress.completed_points, progress.total_points]);

  // Which targets to display on the full-screen surface
  const displayedTargets = useMemo(() => {
    if (mode === "16-point") {
      if (isValidationPhase) {
        return validationPoints.map((pt, i) => ({
          ...pt,
          displayLabel: `V${i + 1}`,
          isValidation: true,
          isDone: progress.completed_points > pt.index,
          isActive: started && !complete && pt.index === activeIndex,
        }));
      }
      return trainingPoints.map((pt) => ({
        ...pt,
        displayLabel: `${pt.index + 1}`,
        isValidation: false,
        isDone: progress.completed_points > pt.index,
        isActive: started && !complete && pt.index === activeIndex,
      }));
    }
    return allPoints.map((pt) => ({
      ...pt,
      displayLabel: `${pt.index + 1}`,
      isValidation: false,
      isDone: progress.completed_points > pt.index,
      isActive: started && !complete && pt.index === activeIndex,
    }));
  }, [
    mode,
    isValidationPhase,
    validationPoints,
    trainingPoints,
    allPoints,
    progress.completed_points,
    started,
    complete,
    activeIndex,
  ]);

  const hasValidationCard = (complete || isValidationFailed) && Boolean(valReport);

  return (
    <main className={styles.surface} aria-label="16-Point Eye Calibration Fullscreen Surface">
      {/* -------------------------------------------------------------------------
          1. Dedicated Full-Viewport Target Layer (Independent of floating panel)
          ------------------------------------------------------------------------- */}
      <section className={styles.targetLayer} aria-label="Calibration coordinate target layer">
        {/* Subtle background crosshairs */}
        <div className={styles.crosshairH} aria-hidden="true" />
        <div className={styles.crosshairV} aria-hidden="true" />

        {/* Validation Phase Notice */}
        {isValidationPhase && (
          <div className={styles.validationPhaseNotice}>
            Independent Validation Phase: 4 Held-Out Verification Targets
          </div>
        )}

        {/* Targets positioned directly on 100vw x 100vh canvas via normalized coordinates */}
        {displayedTargets.map((pt) => {
          const pos = getTargetPosition(pt);
          return (
            <button
              key={`${pt.isValidation ? "val" : "train"}-${pt.index}`}
              id={`target-marker-${pt.displayLabel}`}
              type="button"
              className={[
                styles.targetMarker,
                pt.isDone ? styles.targetDone : "",
                pt.isActive ? styles.targetActive : "",
                pt.isActive ? styles.targetMarkerActive : "",
                pt.isValidation ? styles.targetValidation : "",
                pt.isValidation && pt.isDone ? styles.validationDone : "",
                pt.isValidation && pt.isActive ? styles.validationActive : "",
              ].join(" ")}
              style={{ left: pos.left, top: pos.top }}
              onClick={pt.isActive ? captureCurrentPoint : undefined}
              disabled={!pt.isActive || capturing}
              aria-label={`Target ${pt.displayLabel} at x=${(pt.x * 100).toFixed(1)}%, y=${(pt.y * 100).toFixed(1)}%`}
            >
              <span className={pt.isValidation ? styles.validationDot : styles.pointDot} />
              <span className={pt.isValidation ? styles.validationBadge : styles.pointBadge}>
                {pt.displayLabel}
              </span>
            </button>
          );
        })}
      </section>

      {/* -------------------------------------------------------------------------
          2. Compact, Movable Floating Controller Panel (HUD)
          ------------------------------------------------------------------------- */}
      <aside
        ref={panelRef}
        className={styles.floatingPanel}
        style={
          panelPos
            ? { left: `${panelPos.x}px`, top: `${panelPos.y}px`, bottom: "auto", right: "auto" }
            : {
                bottom: "24px",
                left: defaultPos.docked === "bottom-left" ? "24px" : "auto",
                right: defaultPos.docked === "bottom-right" ? "24px" : "auto",
              }
        }
        aria-label="Calibration Controls"
      >
        {/* Dedicated Drag Handle Bar */}
        <div
          className={[styles.dragHandle, isDragging ? styles.dragging : ""].join(" ")}
          onMouseDown={handleDragMouseDown}
          title="Click and drag to move calibration panel"
        >
          <div className={styles.dragHeaderLeft}>
            <span className={styles.dragGrip} aria-hidden="true">⋮⋮</span>
            <span className={styles.panelTitle}>
              {mode === "16-point" ? "🎯 16-Point Eye Calibration" : "🎯 9-Point Eye Calibration"}
            </span>
          </div>
          <span
            className={styles.phaseBadge}
            style={{ background: phaseInfo.bg, color: phaseInfo.color }}
          >
            {phaseInfo.text}
          </span>
        </div>

        {/* Panel Content Body */}
        <div className={styles.panelBody}>
          {/* Target & Progress Header */}
          <div className={styles.targetInfo}>
            <span className={styles.targetTitle} title={activeTargetDescription}>
              {activeTargetDescription}
            </span>
            <span className={styles.targetStep}>{stepText}</span>
          </div>

          {/* Guidance Message */}
          <div className={styles.guidanceRow}>
            <span
              className={styles.guidanceDot}
              style={{
                background: !started ? "#64748b" : isGuidanceGood ? "#10b981" : "#f59e0b",
              }}
            />
            <span className={styles.guidanceText} title={guidanceMessage}>
              {!started ? "Ready to begin calibration" : guidanceMessage}
            </span>
          </div>

          {/* Compact Progress Bar */}
          <div className={styles.progressTrack} aria-label="Calibration Progress">
            <div
              className={[
                styles.progressFill,
                isValidationPhase ? styles.progressFillValidation : "",
              ].join(" ")}
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Error Notice Banner */}
          {error && (
            <div className={styles.panelError} role="alert">
              ⚠️ {error}
            </div>
          )}

          {/* Validation Metrics Summary when Complete or Failed */}
          {hasValidationCard && (
            <div className={styles.validationSummary}>
              <div className={styles.validationSummaryHeader}>
                <span>Independent Validation Gate</span>
                <span className={valReport.passed ? styles.statusPass : styles.statusFail}>
                  {valReport.passed ? "✓ PASSED" : "🔒 WITHHELD"}
                </span>
              </div>
              <div className={styles.validationGridMini}>
                <div className={styles.validationItemMini}>
                  <span className={styles.validationItemLabel}>Mean Error</span>
                  <span className={styles.validationItemValue}>
                    {valReport.mean_norm_error.toFixed(4)}
                  </span>
                  <span className={styles.validationItemLimit}>Gate: ≤ 0.0800</span>
                </div>
                <div className={styles.validationItemMini}>
                  <span className={styles.validationItemLabel}>Max Error</span>
                  <span className={styles.validationItemValue}>
                    {valReport.max_norm_error.toFixed(4)}
                  </span>
                  <span className={styles.validationItemLimit}>Gate: ≤ 0.1500</span>
                </div>
              </div>

              {Array.isArray(valReport.per_target_norm_errors) && (
                <div>
                  <button
                    type="button"
                    className={styles.btnDetailsToggle}
                    onClick={() => setShowValDetails((prev) => !prev)}
                  >
                    {showValDetails ? "Hide 4-Target Breakdown ▲" : "View 4-Target Breakdown ▼"}
                  </button>
                  {showValDetails && (
                    <div className={styles.validationDetailsPanel}>
                      {valReport.per_target_norm_errors.map((err, i) => (
                        <div key={i} className={styles.validationTargetItem}>
                          <div className={styles.validationTargetTitle}>V{i + 1}</div>
                          <div
                            className={[
                              styles.validationTargetVal,
                              err <= 0.15 ? styles.statusPass : styles.statusFail,
                            ].join(" ")}
                          >
                            {err.toFixed(3)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 9-Point Legacy Quality Card */}
          {complete && mode === "9-point" && quality && (
            <div className={styles.validationSummary}>
              <div className={styles.validationSummaryHeader}>
                <span>9-Point Fit Score</span>
                <span className={quality.score >= 0.7 ? styles.statusPass : styles.statusFail}>
                  {quality.label} ({quality.score.toFixed(2)})
                </span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                RMSE: {quality.rmse.toFixed(3)}
              </div>
            </div>
          )}

          {/* Dynamic Action Controls (Phase-Specific) */}
          <div className={styles.panelActions}>
            {/* Actively Calibrating (Training or Validation) */}
            {started && !complete && !isValidationFailed && (
              <>
                <button
                  id="btn-capture-point"
                  type="button"
                  className={styles.btnPrimary}
                  onClick={captureCurrentPoint}
                  disabled={capturing}
                >
                  {capturing
                    ? "Capturing..."
                    : trackingStatus === "Retry Needed"
                    ? "🔄 Retry Point (ENTER ↵)"
                    : `Press ENTER ↵ (Sample Target ${isValidationPhase ? (activeIndex - 15) : (activeIndex + 1)})`}
                </button>
                <button
                  id="btn-restart-calibration"
                  type="button"
                  className={styles.btnSecondary}
                  onClick={() => restart("16-point")}
                >
                  Restart
                </button>
                <button
                  id="btn-cancel-calibration"
                  type="button"
                  className={styles.btnGhost}
                  onClick={cancel}
                >
                  Cancel (ESC)
                </button>
              </>
            )}

            {/* Ready / Not Started */}
            {!started && !complete && !isValidationFailed && (
              <>
                <button
                  id="btn-start-calibration"
                  type="button"
                  className={styles.btnPrimary}
                  onClick={() => start(mode)}
                  disabled={loading}
                >
                  {loading ? "Connecting..." : "Start Calibration (ENTER ↵)"}
                </button>
                <button
                  id="btn-return-dashboard"
                  type="button"
                  className={styles.btnGhost}
                  onClick={() => { window.location.hash = "#/"; }}
                >
                  ← Dashboard (ESC)
                </button>
              </>
            )}

            {/* Validation Failed */}
            {isValidationFailed && (
              <>
                <button
                  id="btn-restart-calibration"
                  type="button"
                  className={styles.btnPrimary}
                  onClick={() => restart("16-point")}
                >
                  🔄 Restart Calibration (ENTER ↵)
                </button>
                <button
                  id="btn-return-dashboard"
                  type="button"
                  className={styles.btnGhost}
                  onClick={() => { window.location.hash = "#/"; }}
                >
                  Done (ESC)
                </button>
              </>
            )}

            {/* Complete */}
            {complete && (
              <>
                {isAuthorized && (
                  <button
                    id="btn-enable-cursor"
                    type="button"
                    className={cursorEnabled ? styles.btnEnable : styles.btnPrimary}
                    onClick={cursorEnabled ? disableCursor : enableCursor}
                  >
                    {cursorEnabled
                      ? "✓ OS Cursor Takeover Active"
                      : "👁️ Enable System-Wide OS Cursor"}
                  </button>
                )}
                <button
                  id="btn-restart-calibration"
                  type="button"
                  className={styles.btnSecondary}
                  onClick={() => restart("16-point")}
                >
                  Recalibrate
                </button>
                <button
                  id="btn-finish-calibration"
                  type="button"
                  className={styles.btnGhost}
                  onClick={finish}
                >
                  Done (ESC)
                </button>
              </>
            )}
          </div>
        </div>

        {/* Keyboard Hints Footer */}
        <div className={styles.panelHints} aria-hidden="true">
          <span><kbd>ENTER</kbd> Sample/Start</span>
          <span><kbd>ESC</kbd> Cancel/Return</span>
        </div>
      </aside>
    </main>
  );
}
