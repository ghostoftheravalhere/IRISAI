import React from "react";
import styles from "./RuntimeDashboard.module.css";

/**
 * RuntimeDashboard — Health probes, latency histograms, mic status, and active skills
 */
export default function RuntimeDashboard({ health = {}, worldSnapshot = {}, googleAuth = {}, githubAuth = {} }) {
  const isHealthy = health.status === "HEALTHY" || health.status === "online" || health.status === "ok";
  const app = worldSnapshot?.application?.active_app || "System";
  const windowTitle = worldSnapshot?.window?.title || "Desktop";
  const personName = worldSnapshot?.person?.name || (worldSnapshot?.person?.status === "UNKNOWN" ? "Unknown Person" : "No Face Detected");
  const targetName = worldSnapshot?.ui_target?.last_referenced_target?.name || "None";

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.title}>Unified Perception & WorldModel State</span>
        <div className={`${styles.healthBadge} ${isHealthy ? styles.healthy : styles.unhealthy}`}>
          {isHealthy ? "ONLINE" : "OFFLINE"}
        </div>
      </div>

      <div className={styles.grid}>
        <div className={styles.card}>
          <span className={styles.metricLabel}>Recognized Person</span>
          <span className={styles.metricVal}>{personName}</span>
        </div>

        <div className={styles.card}>
          <span className={styles.metricLabel}>Active App & Window</span>
          <span className={styles.metricVal}>{app} — {windowTitle}</span>
        </div>

        <div className={styles.card}>
          <span className={styles.metricLabel}>Screen Grounded Target</span>
          <span className={styles.metricVal}>{targetName}</span>
        </div>

        <div className={styles.card}>
          <span className={styles.metricLabel}>Connected Services</span>
          <span className={styles.metricVal}>
            Google: {googleAuth?.is_connected ? "Connected" : "Disconnected"} | GitHub: {githubAuth?.is_connected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </div>
    </div>
  );
}
