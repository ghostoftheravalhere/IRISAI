/**
 * Toast notifications for voice action feedback.
 */
import { useEffect, useId, useRef, useState } from "react";
import styles from "./Toast.module.css";

const CONTROL_STATUSES = new Set([
  "Idle",
  "Starting",
  "Stopped",
  "Listening",
  "Waiting for push-to-talk",
  "Push-to-talk active",
  "Empty speech",
  "Error",
]);

function classifyToast(message) {
  const text = (message || "").trim();
  if (!text || CONTROL_STATUSES.has(text)) return null;
  if (/is not running\.?$/i.test(text) || /^failed\b/i.test(text) || /^unsupported\b/i.test(text)) {
    return { tone: "warning", label: `⚠ ${text.replace(/\.$/, "")}` };
  }
  if (/^unknown command/i.test(text)) {
    return { tone: "warning", label: `⚠ ${text}` };
  }
  return { tone: "success", label: `✓ ${text}` };
}

export function useVoiceToasts(executionStatus, latestTranscript) {
  const [toasts, setToasts] = useState([]);
  const primed = useRef(false);
  const lastKey = useRef("");

  useEffect(() => {
    const classified = classifyToast(executionStatus);
    const key = `${executionStatus || ""}|${latestTranscript || ""}`;

    if (!primed.current) {
      primed.current = true;
      lastKey.current = key;
      return undefined;
    }

    if (!classified || key === lastKey.current) {
      return undefined;
    }

    lastKey.current = key;
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev.slice(-4), { id, ...classified }]);

    const timer = setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 3200);
    return () => clearTimeout(timer);
  }, [executionStatus, latestTranscript]);

  const dismiss = (id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  return { toasts, dismiss };
}

export default function ToastStack({ toasts, onDismiss }) {
  const titleId = useId();

  if (!toasts.length) return null;

  return (
    <div className={styles.stack} aria-live="polite" aria-relevant="additions">
      <span id={titleId} className={styles.srOnly}>
        Voice action notifications
      </span>
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={toast.tone === "warning" ? styles.toastWarning : styles.toastSuccess}
          role="status"
        >
          <span className={styles.message}>{toast.label}</span>
          <button
            type="button"
            className={styles.dismiss}
            aria-label="Dismiss notification"
            onClick={() => onDismiss(toast.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
