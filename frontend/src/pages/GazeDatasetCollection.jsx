import { useState, useEffect } from "react";
import axios from "axios";
import styles from "./GazeDatasetCollection.module.css";

const API_BASE = "http://127.0.0.1:8000/api/v1/dataset/gaze";

export default function GazeDatasetCollection() {
  const [userId, setUserId] = useState("user_01");
  const [sessionId, setSessionId] = useState("");
  const [status, setStatus] = useState({
    active: false,
    current_target_index: 0,
    targets: [],
    total_accepted: 0,
    total_rejected: 0,
    progress_percent: 0,
  });
  const [validation, setValidation] = useState(null);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/status`);
      setStatus(res.data);
    } catch (err) {
      console.error("Failed to fetch gaze dataset status", err);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleStartSession = async () => {
    try {
      const res = await axios.post(`${API_BASE}/session/start`, {
        user_id: userId,
        session_id: sessionId || undefined,
      });
      setStatus(res.data);
    } catch (err) {
      console.error("Failed to start session", err);
    }
  };

  const handleStopSession = async () => {
    try {
      const res = await axios.post(`${API_BASE}/session/stop`);
      setStatus(res.data);
    } catch (err) {
      console.error("Failed to stop session", err);
    }
  };

  const handleValidate = async () => {
    try {
      const res = await axios.get(`${API_BASE}/validate`);
      setValidation(res.data);
    } catch (err) {
      console.error("Failed to validate dataset", err);
    }
  };

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Eye Gaze Dataset Collector</h1>
          <p className={styles.subtitle}>
            Collect paired eye image crops and screen target coordinates for ML training
          </p>
        </div>
      </header>

      <div className={styles.panel}>
        <div className={styles.controls}>
          <div className={styles.inputGroup}>
            <label>User ID (Anti-Leakage Partition)</label>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              disabled={status.active}
            />
          </div>

          <div className={styles.inputGroup}>
            <label>Session ID (Optional)</label>
            <input
              type="text"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="Auto-generated if empty"
              disabled={status.active}
            />
          </div>

          {!status.active ? (
            <button className={styles.btnPrimary} onClick={handleStartSession}>
              Start Collection Session
            </button>
          ) : (
            <button className={styles.btnSecondary} onClick={handleStopSession}>
              Stop Session
            </button>
          )}

          <button className={styles.btnSecondary} onClick={handleValidate}>
            Validate Dataset
          </button>
        </div>
      </div>

      <div className={styles.panel}>
        <h3>Target Screen Grid (30 Usable Samples / Point)</h3>
        <div className={styles.grid}>
          {status.targets.map((t) => {
            const isActive = status.active && t.index === status.current_target_index;
            return (
              <div
                key={t.index}
                className={`${styles.targetCell} ${isActive ? styles.targetActive : ""}`}
              >
                {isActive && <div className={styles.dot} />}
                <strong>{t.name}</strong>
                <span className={styles.countLabel}>
                  {t.accepted} / {t.target_limit} Accepted ({t.rejected} Rejected)
                </span>
              </div>
            );
          })}
        </div>

        <div className={styles.stats}>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{status.total_accepted}</div>
            <div className={styles.statLabel}>Total Accepted Samples</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{status.total_rejected}</div>
            <div className={styles.statLabel}>Total Rejected Samples</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{status.progress_percent}%</div>
            <div className={styles.statLabel}>Overall Progress</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{status.active ? "COLLECTING" : "IDLE"}</div>
            <div className={styles.statLabel}>Collection State</div>
          </div>
        </div>
      </div>

      {validation && (
        <div className={styles.panel}>
          <h3>Dataset Integrity Validation Report</h3>
          <p>Valid: <strong>{validation.is_valid ? "YES" : "NO"}</strong></p>
          <p>Total Users: {validation.total_users} | Total Sessions: {validation.total_sessions} | Total Samples: {validation.total_samples}</p>
          {validation.issues.length > 0 && (
            <div>
              <h4>Detected Issues:</h4>
              <ul>
                {validation.issues.map((issue, idx) => (
                  <li key={idx}>{issue}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
