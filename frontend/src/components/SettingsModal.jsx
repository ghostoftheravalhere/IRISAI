import React, { useState } from "react";
import styles from "./SettingsModal.module.css";

/**
 * SettingsModal — Comprehensive Settings Dialog
 */
export default function SettingsModal({ isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState("voice");
  const [wakeWordEnabled, setWakeWordEnabled] = useState(true);
  const [theme, setTheme] = useState("dark");
  const [privacyLevel, setPrivacyLevel] = useState("strict_local");

  if (!isOpen) return null;

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <span className={styles.modalTitle}>IRIS AI System Settings</span>
          <button className={styles.closeBtn} onClick={onClose}>
            ✕
          </button>
        </div>

        <div className={styles.modalBody}>
          <div className={styles.tabsNav}>
            {["voice", "wakeWord", "theme", "memory", "reasoning", "skills", "privacy", "accessibility"].map((tab) => (
              <button
                key={tab}
                className={`${styles.tabBtn} ${activeTab === tab ? styles.activeTab : ""}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          <div className={styles.tabContent}>
            {activeTab === "voice" && (
              <div className={styles.settingGroup}>
                <label className={styles.label}>Microphone Input Device</label>
                <select className={styles.select}>
                  <option>Default Hardware Microphone (Windows WASAPI)</option>
                  <option>Realtek High Definition Audio</option>
                </select>

                <label className={styles.label}>VAD Sensitivity Threshold</label>
                <input type="range" min="0.1" max="0.9" step="0.1" defaultValue="0.5" className={styles.range} />
              </div>
            )}

            {activeTab === "wakeWord" && (
              <div className={styles.settingGroup}>
                <label className={styles.toggleRow}>
                  <span>Enable Wake Word ("Hey IRIS")</span>
                  <input
                    type="checkbox"
                    checked={wakeWordEnabled}
                    onChange={(e) => setWakeWordEnabled(e.target.checked)}
                  />
                </label>
              </div>
            )}

            {activeTab === "theme" && (
              <div className={styles.settingGroup}>
                <label className={styles.label}>Appearance Theme</label>
                <select className={styles.select} value={theme} onChange={(e) => setTheme(e.target.value)}>
                  <option value="dark">Glassmorphism Dark (Default)</option>
                  <option value="oled">OLED Deep Black</option>
                  <option value="cyberpunk">Cyberpunk Neon</option>
                </select>
              </div>
            )}

            {activeTab === "privacy" && (
              <div className={styles.settingGroup}>
                <label className={styles.label}>Privacy & Telemetry Mode</label>
                <select
                  className={styles.select}
                  value={privacyLevel}
                  onChange={(e) => setPrivacyLevel(e.target.value)}
                >
                  <option value="strict_local">Strict Local Only (No Data Egress)</option>
                  <option value="anonymized_telemetry">Anonymized Local Diagnostics</option>
                </select>
              </div>
            )}

            {["memory", "reasoning", "skills", "accessibility"].includes(activeTab) && (
              <div className={styles.settingGroup}>
                <div className={styles.infoBox}>
                  Configuration for <strong>{activeTab}</strong> is set to default production baseline.
                </div>
              </div>
            )}
          </div>
        </div>

        <div className={styles.modalFooter}>
          <button className={styles.saveBtn} onClick={onClose}>
            Save & Close
          </button>
        </div>
      </div>
    </div>
  );
}
