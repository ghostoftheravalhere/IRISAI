import { useState, useEffect } from "react";
import axios from "axios";
import styles from "./GazeHud.module.css";

const API_HUD = "http://127.0.0.1:8000/eye/hud";

export default function GazeHud() {
  const [hudState, setHudState] = useState({
    gaze_x: 0.5,
    gaze_y: 0.5,
    confidence: 0.0,
    tracking_state: "lost",
    ptt_state: "idle",
  });

  useEffect(() => {
    const fetchHud = async () => {
      try {
        const res = await axios.get(API_HUD);
        setHudState(res.data);
      } catch (err) {
        // Silently ignore poll errors when backend is offline
      }
    };

    fetchHud();
    const interval = setInterval(fetchHud, 100);
    return () => clearInterval(interval);
  }, []);

  const leftPx = `${hudState.gaze_x * 100}%`;
  const topPx = `${hudState.gaze_y * 100}%`;

  const statusClass =
    hudState.tracking_state === "active"
      ? styles.indicatorActive
      : hudState.tracking_state === "low_confidence"
      ? styles.indicatorLow
      : styles.indicatorLost;

  return (
    <div className={styles.hudContainer} aria-hidden="true">
      {hudState.tracking_state !== "lost" && (
        <div className={styles.gazeTarget} style={{ left: leftPx, top: topPx }}>
          <div className={styles.crosshair} />
        </div>
      )}

      <div className={styles.statusPill}>
        <span className={statusClass} />
        <span>
          {hudState.tracking_state === "active"
            ? `Tracking (${Math.round(hudState.confidence * 100)}%)`
            : hudState.tracking_state === "low_confidence"
            ? "Low Confidence"
            : "Tracking Lost"}
        </span>
        {hudState.ptt_state === "listening" && <strong> · Listening...</strong>}
      </div>
    </div>
  );
}
