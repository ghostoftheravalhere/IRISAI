import React, { useState } from "react";
import VoiceVisualizer from "./VoiceVisualizer";
import styles from "./FloatingAssistant.module.css";

/**
 * FloatingAssistant — Always-on-top draggable HUD overlay
 */
export default function FloatingAssistant({
  voiceState = "IDLE",
  activeApp = "System",
  currentCommand = "",
  onToggleExpand,
  isExpanded = false,
  onOpenSettings,
}) {
  const [position, setPosition] = useState({ x: 40, y: 40 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const handleMouseDown = (e) => {
    setIsDragging(true);
    setDragOffset({
      x: e.clientX - position.x,
      y: e.clientY - position.y,
    });
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;
    setPosition({
      x: Math.max(10, Math.min(window.innerWidth - 300, e.clientX - dragOffset.x)),
      y: Math.max(10, Math.min(window.innerHeight - 100, e.clientY - dragOffset.y)),
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  return (
    <div
      className={`${styles.hudPill} ${isExpanded ? styles.expanded : styles.compact}`}
      style={{ left: `${position.x}px`, top: `${position.y}px` }}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      <div className={styles.dragHeader} onMouseDown={handleMouseDown}>
        <div className={styles.dragGrip}>:::</div>
        <div className={styles.titleGroup}>
          <span className={styles.brand}>IRIS AI</span>
          <span className={styles.activeAppTag}>{activeApp}</span>
        </div>
        <div className={styles.controls}>
          <button className={styles.iconBtn} onClick={onToggleExpand} title="Toggle Expand">
            {isExpanded ? "↙" : "↗"}
          </button>
          <button className={styles.iconBtn} onClick={onOpenSettings} title="Settings">
            ⚙
          </button>
        </div>
      </div>

      <div className={styles.contentBody}>
        <VoiceVisualizer voiceState={voiceState} />
        {currentCommand && <div className={styles.commandBanner}>{currentCommand}</div>}
      </div>
    </div>
  );
}
