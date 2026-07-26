/**
 * Supported voice commands reference panel.
 */
import styles from "./VoiceCommandsHelp.module.css";

const COMMAND_GROUPS = [
  {
    title: "Applications",
    commands: [
      { phrase: "Open Chrome", description: "Launches Google Chrome." },
      { phrase: "Close Chrome", description: "Closes Google Chrome." },
      { phrase: "Open Notepad", description: "Launches Notepad." },
      { phrase: "Close Notepad", description: "Closes Notepad." },
      { phrase: "Open Edge", description: "Launches Microsoft Edge." },
      { phrase: "Close Edge", description: "Closes Microsoft Edge." },
    ],
  },
  {
    title: "Window",
    commands: [
      { phrase: "Close Window", description: "Closes the currently focused window." },
      { phrase: "Minimize Window", description: "Minimizes the active window." },
    ],
  },
  {
    title: "Navigation",
    commands: [
      { phrase: "Scroll Up", description: "Scrolls the active page upward." },
      { phrase: "Scroll Down", description: "Scrolls the active page downward." },
    ],
  },
  {
    title: "Clipboard",
    commands: [
      { phrase: "Copy", description: "Copies the current selection." },
      { phrase: "Paste", description: "Pastes from the clipboard." },
    ],
  },
  {
    title: "System",
    commands: [
      { phrase: "Screenshot", description: "Captures and saves a screenshot." },
      { phrase: "Volume Up", description: "Increases system volume." },
      { phrase: "Volume Down", description: "Decreases system volume." },
      { phrase: "Mute", description: "Toggles system mute." },
    ],
  },
];

export default function VoiceCommandsHelp({ open, onToggle }) {
  return (
    <section className={styles.panel} aria-label="Supported voice commands">
      <div className={styles.header}>
        <div>
          <h3 className={styles.title}>Supported Voice Commands</h3>
          <p className={styles.subtitle}>
            Speak clearly after starting voice recognition.
          </p>
        </div>
        <button
          type="button"
          className={styles.helpButton}
          onClick={onToggle}
          aria-expanded={open}
        >
          {open ? "Hide Help" : "Help"}
        </button>
      </div>

      {open && (
        <div className={styles.body}>
          {COMMAND_GROUPS.map((group) => (
            <div key={group.title} className={styles.group}>
              <h4 className={styles.groupTitle}>{group.title}</h4>
              <ul className={styles.list}>
                {group.commands.map((command) => (
                  <li key={command.phrase} className={styles.item}>
                    <div className={styles.phraseRow}>
                      <span className={styles.mic} aria-hidden="true">
                        🎤
                      </span>
                      <span className={styles.phrase}>{command.phrase}</span>
                    </div>
                    <p className={styles.description}>{command.description}</p>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
