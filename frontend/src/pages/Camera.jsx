import { useCameraStatus } from "../hooks/useCameraStatus";
import cameraService from "../services/cameraService";
import styles from "./Camera.module.css";

export default function Camera() {
  const { connected, running, loading, error, start, stop, refresh } = useCameraStatus();
  const streamUrl = cameraService.getStreamUrl();

  return (
    <main className={styles.container}>
      <div className={styles.card}>
        <h2 className={styles.heading}>Camera Module</h2>

        <section className={styles.previewSection} aria-label="Camera Preview">
          <h3 className={styles.previewHeading}>Camera Preview</h3>
          <div className={styles.previewCard}>
            {running ? (
              <img
                className={styles.previewImage}
                src={streamUrl}
                alt="Live camera preview"
              />
            ) : (
              <div className={styles.previewPlaceholder}>No Camera Feed</div>
            )}
          </div>
        </section>

        <div className={styles.statusRow}>
          <span className={connected ? styles.dotOnline : styles.dotOffline} />
          <span className={styles.statusText}>
            {connected ? "Camera Connected" : "Camera Not Connected"}
          </span>
        </div>

        <div className={styles.statusRow}>
          <span className={running ? styles.dotOnline : styles.dotOffline} />
          <span className={styles.statusText}>
            {running ? "Camera Running" : "Camera Stopped"}
          </span>
        </div>

        {error && <p className={styles.error}>{error}</p>}

        <div className={styles.actions}>
          <button
            className={styles.btnPrimary}
            onClick={start}
            disabled={loading || running}
          >
            Start Camera
          </button>
          <button
            className={styles.btnSecondary}
            onClick={stop}
            disabled={loading || !running}
          >
            Stop Camera
          </button>
          <button
            className={styles.btnGhost}
            onClick={refresh}
            disabled={loading}
          >
            Refresh
          </button>
        </div>
      </div>
    </main>
  );
}
