import { useCalibrationWizard } from "../hooks/useCalibrationWizard";
import styles from "./Calibration.module.css";

const CALIBRATION_POINTS = [
  "Top Left",
  "Top Center",
  "Top Right",
  "Middle Left",
  "Center",
  "Middle Right",
  "Bottom Left",
  "Bottom Center",
  "Bottom Right",
];

export default function Calibration() {
  const {
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
    restart,
    start,
  } = useCalibrationWizard();

  const complete = progress.complete;
  const currentPoint = complete ? "Complete" : CALIBRATION_POINTS[activeIndex] ?? "Waiting";
  const quality = progress.quality;

  const guidanceMessage = guidance?.message ?? "Center your face in front of camera";
  const isGuidanceGood = guidance?.status === "good" && guidance?.is_stable;

  const qualityMessage = (() => {
    if (!quality) {
      return null;
    }

    const label = quality.label.charAt(0).toUpperCase() + quality.label.slice(1);
    const scoreText = quality.score.toFixed(2);
    const rmseText =
      typeof quality.rmse === "number" ? `, RMSE ${quality.rmse.toFixed(3)}` : "";

    if (quality.label === "good") {
      return `${label} (score ${scoreText}${rmseText}) — cursor tracking looks solid for this webcam.`;
    }
    if (quality.label === "fair") {
      return `${label} (score ${scoreText}${rmseText}) — cursor is usable; corner accuracy may vary.`;
    }
    return `${label} (score ${scoreText}${rmseText}) — recalibration recommended before enabling cursor.`;
  })();

  return (
    <main className={styles.container}>
      <section className={styles.overlay} aria-labelledby="calibration-title">
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>Eye Calibration</p>
            <h1 id="calibration-title" className={styles.title}>
              {complete ? "Calibration Complete" : "Look directly at the highlighted dot."}
            </h1>
          </div>
          <div className={styles.progressPanel} aria-label="Calibration progress">
            <span className={styles.progressText}>{progressText}</span>
            <div className={styles.progressTrack}>
              <div
                className={styles.progressFill}
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        </header>

        <section className={styles.statusBar} aria-label="Calibration status">
          <div>
            <span className={styles.statusLabel}>Current Point</span>
            <strong>{currentPoint}</strong>
          </div>
          <div>
            <span className={styles.statusLabel}>Tracking Status</span>
            <strong>{trackingStatus}</strong>
          </div>
          <div>
            <span className={styles.statusLabel}>Posture Guidance</span>
            <strong style={{ color: isGuidanceGood ? "#34d399" : "#fbbf24" }}>
              {started ? guidanceMessage : "Ready"}
            </strong>
          </div>
          <div>
            <span className={styles.statusLabel}>Calibration Status</span>
            <strong>{complete ? "Complete" : started ? "In Progress" : "Ready"}</strong>
          </div>
        </section>

        <section className={styles.grid} aria-label="Nine calibration points">
          {CALIBRATION_POINTS.map((label, index) => {
            const isDone = index < progress.completed_points;
            const isActive = started && !complete && index === activeIndex;

            return (
              <button
                key={label}
                type="button"
                className={[
                  styles.pointCell,
                  isDone ? styles.pointDone : "",
                  isActive ? styles.pointActive : "",
                ].join(" ")}
                onClick={isActive ? captureCurrentPoint : undefined}
                disabled={!isActive || capturing}
                aria-label={`${label} calibration point`}
              >
                <span className={styles.pointDot} />
              </button>
            );
          })}
        </section>

        {error && <p className={styles.error}>{error}</p>}
        {complete && qualityMessage && (
          <p className={quality?.recommend_recalibration ? styles.error : styles.statusLabel}>
            {qualityMessage}
          </p>
        )}

        <footer className={styles.actions}>
          <button
            type="button"
            className={styles.btnPrimary}
            onClick={start}
            disabled={started && !complete}
          >
            Start Calibration
          </button>
          <button
            type="button"
            className={styles.btnSecondary}
            onClick={captureCurrentPoint}
            disabled={!started || complete || capturing}
          >
            {capturing ? "Capturing..." : "Capture Point"}
          </button>
          <button type="button" className={styles.btnSecondary} onClick={restart}>
            Restart
          </button>
          <button
            type="button"
            className={styles.btnGhost}
            onClick={cancel}
            disabled={!started}
          >
            Cancel
          </button>
          <button
            type="button"
            className={styles.btnGhost}
            onClick={finish}
            disabled={!complete}
          >
            Finish
          </button>
          <button
            type="button"
            className={cursorEnabled ? styles.btnEnable : styles.btnSecondary}
            onClick={cursorEnabled ? disableCursor : enableCursor}
            disabled={!complete && !cursorEnabled}
          >
            {cursorEnabled ? "✓ OS Cursor Takeover Active" : "Enable System-Wide OS Cursor"}
          </button>
        </footer>
      </section>
    </main>
  );
}
