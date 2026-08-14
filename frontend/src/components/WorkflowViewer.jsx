import React from "react";
import styles from "./WorkflowViewer.module.css";

/**
 * WorkflowViewer — Real-time TaskPlan step progress graph viewer
 */
export default function WorkflowViewer({ activePlan = null }) {
  if (!activePlan) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>Workflow Execution Graph</div>
        <div className={styles.emptyState}>No active workflow. Execute a voice or browser/settings command.</div>
      </div>
    );
  }

  const getStepStatusClass = (status) => {
    switch (status) {
      case "COMPLETED":
        return styles.completed;
      case "IN_PROGRESS":
        return styles.inProgress;
      case "FAILED":
        return styles.failed;
      case "PENDING":
      default:
        return styles.pending;
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case "COMPLETED":
        return "✓";
      case "IN_PROGRESS":
        return "⏳";
      case "FAILED":
        return "✕";
      case "PENDING":
      default:
        return "○";
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.planTitle}>{activePlan.name || "TaskPlan Execution"}</span>
        <span className={styles.planId}>ID: {activePlan.plan_id ? activePlan.plan_id.slice(0, 8) : "Active"}</span>
      </div>

      <div className={styles.stepsList}>
        {activePlan.steps.map((step, idx) => (
          <div key={idx} className={`${styles.stepRow} ${getStepStatusClass(step.status)}`}>
            <div className={styles.stepBadge}>{getStatusIcon(step.status)}</div>
            <div className={styles.stepInfo}>
              <div className={styles.intentName}>{step.intent}</div>
              <div className={styles.targetName}>
                Target: {step.target || "N/A"}
                {step.params && Object.keys(step.params).length > 0 && (
                  <span className={styles.paramsTag}> params: {JSON.stringify(step.params)}</span>
                )}
              </div>
            </div>
            <div className={styles.stepStatusText}>{step.status}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
