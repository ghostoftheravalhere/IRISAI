import React, { useState } from "react";
import styles from "./ConversationPanel.module.css";

/**
 * ConversationPanel — Chat history, voice transcripts, and command logs
 */
export default function ConversationPanel({ history = [], onSendTextCommand }) {
  const [inputText, setInputText] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    onSendTextCommand(inputText.trim());
    setInputText("");
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>Conversation & Command Log</span>
        <span className={styles.count}>{history.length} items</span>
      </div>

      <div className={styles.feed}>
        {history.length === 0 ? (
          <div className={styles.emptyState}>No recent voice or text commands yet. Speak or type below.</div>
        ) : (
          history.map((item, idx) => (
            <div key={idx} className={`${styles.card} ${styles[item.type]}`}>
              <div className={styles.cardHeader}>
                <span className={styles.sourceBadge}>{item.source || "VOICE"}</span>
                <span className={styles.timestamp}>{item.timestamp}</span>
              </div>
              <div className={styles.transcript}>{item.transcript || item.text}</div>
              {item.intent && <div className={styles.intentTag}>Intent: {item.intent}</div>}
              {item.response && <div className={styles.responseMsg}>{item.response}</div>}
            </div>
          ))
        )}
      </div>

      <form className={styles.inputForm} onSubmit={handleSubmit}>
        <input
          type="text"
          className={styles.inputField}
          placeholder="Type a command (e.g., Open settings search camera)..."
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
        />
        <button type="submit" className={styles.sendBtn}>
          Send
        </button>
      </form>
    </div>
  );
}
