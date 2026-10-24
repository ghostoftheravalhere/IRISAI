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
  cursorControlActive = false,
  onToggleCursor,
}) {
  return (
    <div className={styles.trayBar}>
      <div className={styles.brandGroup}>
        <span
          className={styles.statusDot}
          style={cursorControlActive ? { background: "var(--accent-green)", boxShadow: "0 0 8px var(--accent-green)" } : undefined}
        />
        <span className={styles.statusText}>{cursorControlActive ? "Cursor Active" : "IRIS AI Active"}</span>
      </div>

      <div className={styles.trayActions}>
        {onToggleCursor && (
          <button
            id="tray-cursor-toggle-btn"
            className={styles.trayBtn}
            onClick={onToggleCursor}
            title={cursorControlActive ? "Pause Eye Cursor Control (Alt+C)" : "Start Eye Cursor Control (Alt+C)"}
            style={cursorControlActive ? {
              background: "rgba(239, 68, 68, 0.2)",
              color: "#f87171",
              borderColor: "rgba(239, 68, 68, 0.4)",
              fontWeight: "700",
            } : {
              background: "rgba(16, 185, 129, 0.15)",
              color: "#34d399",
              borderColor: "rgba(16, 185, 129, 0.35)",
              fontWeight: "700",
            }}
          >
            {cursorControlActive ? "⏸️ Pause Cursor (Alt+C)" : "👁️ Start Cursor (Alt+C)"}
          </button>
        )}

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
