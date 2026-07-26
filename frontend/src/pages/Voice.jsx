import { useState } from "react";
import ToastStack, { useVoiceToasts } from "../components/Toast";
import VoiceCommandsHelp from "../components/VoiceCommandsHelp";
import { useVoiceStatus } from "../hooks/useVoiceStatus";
import styles from "./Voice.module.css";

export default function Voice() {
  const {
    microphoneStatus,
    listening,
    listenMode,
    pushToTalkActive,
    latestTranscript,
    detectedIntent,
    executionStatus,
    loading,
    error,
    start,
    stop,
    setMode,
    pushToTalkStart,
    pushToTalkStop,
    refresh,
  } = useVoiceStatus();
  const [helpOpen, setHelpOpen] = useState(true);
  const { toasts, dismiss } = useVoiceToasts(executionStatus, latestTranscript);

  const listeningLabel = listening
    ? pushToTalkActive
      ? "Listening (PTT)"
      : listenMode === "push_to_talk"
        ? "Armed — hold Push to Talk"
        : "Listening"
    : "Not Listening";

  return (
    <main className={styles.container}>
      <div className={styles.layout}>
        <div className={styles.card}>
          <h2 className={styles.heading}>Voice Commands</h2>
          <p className={styles.subtitle}>
            Offline Faster-Whisper commands through the shared ActionEngine pipeline.
          </p>

          <div className={styles.statusRow}>
            <span
              className={
                listening ? styles.dotListening : styles.dotOffline
              }
              data-active={listening ? "true" : "false"}
            />
            <span className={styles.statusText}>{listeningLabel}</span>
          </div>

          <div className={styles.metaGrid}>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>Microphone</span>
              <span className={styles.metaValue}>{microphoneStatus}</span>
            </div>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>Voice status</span>
              <span className={styles.metaValue}>{executionStatus}</span>
            </div>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>Mode</span>
              <span className={styles.metaValue}>
                {listenMode === "push_to_talk" ? "Push to Talk" : "Continuous"}
              </span>
            </div>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>Last intent</span>
              <span className={styles.metaValue}>{detectedIntent ?? "—"}</span>
            </div>
          </div>

          <section className={styles.commandPanel} aria-label="Last recognized command">
            <h3 className={styles.panelHeading}>Last recognized command</h3>
            <p className={styles.commandText}>
              {latestTranscript || "Say a command after starting voice."}
            </p>
          </section>

          {error && <p className={styles.error}>{error}</p>}

          <div className={styles.modeRow}>
            <button
              type="button"
              className={
                listenMode === "continuous" ? styles.modeActive : styles.modeButton
              }
              onClick={() => setMode("continuous")}
              disabled={loading}
            >
              Continuous
            </button>
            <button
              type="button"
              className={
                listenMode === "push_to_talk" ? styles.modeActive : styles.modeButton
              }
              onClick={() => setMode("push_to_talk")}
              disabled={loading}
            >
              Push to Talk
            </button>
          </div>

          <div className={styles.actions}>
            <button
              type="button"
              className={styles.btnPrimary}
              onClick={() => start(listenMode)}
              disabled={loading || listening}
            >
              Start Voice
            </button>
            <button
              type="button"
              className={styles.btnSecondary}
              onClick={stop}
              disabled={loading || !listening}
            >
              Stop Voice
            </button>
            {listenMode === "push_to_talk" && (
              <button
                type="button"
                className={styles.btnPtt}
                onMouseDown={pushToTalkStart}
                onMouseUp={pushToTalkStop}
                onMouseLeave={pushToTalkStop}
                onTouchStart={(event) => {
                  event.preventDefault();
                  pushToTalkStart();
                }}
                onTouchEnd={(event) => {
                  event.preventDefault();
                  pushToTalkStop();
                }}
                disabled={loading || !listening}
              >
                {pushToTalkActive ? "Release to Send" : "Hold to Talk"}
              </button>
            )}
            <button
              type="button"
              className={styles.btnGhost}
              onClick={refresh}
              disabled={loading}
            >
              Refresh
            </button>
          </div>
        </div>

        <VoiceCommandsHelp
          open={helpOpen}
          onToggle={() => setHelpOpen((value) => !value)}
        />
      </div>

      <ToastStack toasts={toasts} onDismiss={dismiss} />
    </main>
  );
}
