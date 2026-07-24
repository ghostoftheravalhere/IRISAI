import { useBackendStatus } from "../hooks/useBackendStatus";
import { useCameraStatus } from "../hooks/useCameraStatus";
import StatusCard from "../components/StatusCard";
import styles from "./Dashboard.module.css";

export default function Dashboard() {
  const { online, version } = useBackendStatus();
  const { connected, running } = useCameraStatus();

  return (
    <main className={styles.container}>
      <div className={styles.card}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>👁</span>
          <h1 className={styles.title}>IRIS AI</h1>
          <p className={styles.subtitle}>Intelligent Responsive Interface System</p>
        </div>

        <div className={styles.divider} />

        {/* Backend status */}
        <div className={styles.statusRow}>
          <span className={online ? styles.dotOnline : styles.dotOffline} />
          <span className={styles.statusText}>
            {online ? "Backend Online" : "Backend Offline"}
          </span>
        </div>

        {version && <p className={styles.version}>v{version}</p>}

        <div className={styles.divider} />

        {/* System status cards */}
        <div className={styles.cards}>
          <StatusCard
            title="Camera"
            online={connected && running}
            label={connected && running ? "Camera Ready" : "Camera Offline"}
          />
        </div>
      </div>
    </main>
  );
}
