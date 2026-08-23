import React from "react";
import styles from "./VoiceVisualizer.module.css";

/**
 * VoiceVisualizer — 5-state voice animation component
 * States: IDLE, LISTENING, THINKING, SPEAKING, WAKE_WORD
 */
export default function VoiceVisualizer({ voiceState = "IDLE", audioLevel = 0.5 }) {
  const getOrbClass = () => {
    switch (voiceState) {
      case "LISTENING":
        return `${styles.orb} ${styles.listening}`;
      case "THINKING":
        return `${styles.orb} ${styles.thinking}`;
      case "SPEAKING":
        return `${styles.orb} ${styles.speaking}`;
      case "WAKE_WORD":
        return `${styles.orb} ${styles.wakeWord}`;
      case "IDLE":
      default:
        return `${styles.orb} ${styles.idle}`;
    }
  };

  return (
    <div className={styles.container}>
      <div className={getOrbClass()}>
        <div className={styles.core} />
      </div>
      {voiceState === "LISTENING" && (
        <div className={styles.waveGroup}>
          {[0.8, 1.2, 0.6, 1.5, 0.9].map((scale, i) => (
            <div
              key={i}
              className={styles.bar}
              style={{
                height: `${Math.max(8, Math.min(32, audioLevel * 30 * scale))}px`,
                animationDelay: `${i * 0.1}s`,
              }}
            />
          ))}
        </div>
      )}
      <div className={styles.stateLabel}>{voiceState}</div>
    </div>
  );
}
