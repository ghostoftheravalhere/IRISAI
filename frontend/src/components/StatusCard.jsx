/**
 * StatusCard
 * Reusable status indicator card.
 *
 * Props:
 *   title    string   — card heading
 *   online   boolean  — green dot when true, red when false
 *   label    string   — status label text
 *   children node     — optional extra content below the status row
 */
import styles from "./StatusCard.module.css";

export default function StatusCard({ title, online, label, children }) {
  return (
    <div className={styles.card}>
      <p className={styles.title}>{title}</p>
      <div className={styles.statusRow}>
        <span className={online ? styles.dotOnline : styles.dotOffline} />
        <span className={styles.statusText}>{label}</span>
      </div>
      {children}
    </div>
  );
}
