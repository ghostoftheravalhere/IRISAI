import React from "react";
import styles from "./SystemTray.module.css";

/**
 * SystemTray — Quick Action Bar & Microphone Mute Controls
 */
export default function SystemTray({
  isMicMuted = false,
  onToggleMute,
  onOpenSettings,
  onRestartBackend,
}) {
  return (
    <div className={styles.trayBar}>
      <div className={styles.brandGroup}>
        <span className={styles.statusDot} />
        <span className={styles.statusText}>IRIS V3 Active</span>
      </div>

      <div className={styles.trayActions}>
        <button
          className={`${styles.trayBtn} ${isMicMuted ? styles.muted : ""}`}
          onClick={onToggleMute}
          title={isMicMuted ? "Unmute Microphone" : "Mute Microphone"}
        >
          {isMicMuted ? "🎙 Muted" : "🎙 Mic Active"}
        </button>

        <button className={styles.trayBtn} onClick={onOpenSettings} title="Settings">
          ⚙ Settings
        </button>

        <button className={styles.trayBtn} onClick={onRestartBackend} title="Restart Backend">
          🔄 Restart Backend
        </button>
      </div>
    </div>
  );
}
