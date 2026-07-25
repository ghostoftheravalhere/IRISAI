import { useCameraStatus } from "../hooks/useCameraStatus";
import styles from "./Camera.module.css";

export default function Camera() {
  const { connected, running, loading, error, start, stop, refresh } = useCameraStatus();

  return (
    <main className={styles.container}>
      <div className={styles.card}>
        <h2 className={styles.heading}>Camera Module</h2>

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
            Start
          </button>
          <button
            className={styles.btnSecondary}
            onClick={stop}
            disabled={loading || !running}
          >
            Stop
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
