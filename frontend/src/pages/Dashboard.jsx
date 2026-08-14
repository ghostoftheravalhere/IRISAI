import React, { useState, useEffect } from "react";
import FloatingAssistant from "../components/FloatingAssistant";
import ConversationPanel from "../components/ConversationPanel";
import WorkflowViewer from "../components/WorkflowViewer";
import RuntimeDashboard from "../components/RuntimeDashboard";
import SettingsModal from "../components/SettingsModal";
import SystemTray from "../components/SystemTray";
import { IRISApiClient, IRISWebSocketClient } from "../services/api_client";
import styles from "./Dashboard.module.css";

export default function Dashboard() {
  const [voiceState, setVoiceState] = useState("IDLE");
  const [activeApp, setActiveApp] = useState("System");
  const [currentCommand, setCurrentCommand] = useState("");
  const [history, setHistory] = useState([
    {
      source: "VOICE",
      timestamp: "19:35:10",
      transcript: "Open settings search for camera",
      intent: "BROWSER_SEARCH",
      response: "Executed TaskPlan for 'camera' search in settings",
    },
  ]);
  const [activePlan, setActivePlan] = useState({
    name: "Application Search 'camera' in settings",
    plan_id: "7eaea646-f4cd-4bf8-b0ff-f43909d81662",
    steps: [
      { intent: "OPEN_APPLICATION", target: "settings", status: "COMPLETED" },
      { intent: "WAIT_FOR_WINDOW", target: "settings", status: "COMPLETED" },
      { intent: "ACTIVATE_WINDOW", target: "settings", status: "COMPLETED" },
      { intent: "VERIFY_WINDOW_ACTIVE", target: "settings", status: "COMPLETED" },
      { intent: "HOTKEY", target: "settings", params: { keys: ["ctrl", "f"] }, status: "COMPLETED" },
      { intent: "TYPE_TEXT", target: "settings", params: { text: "camera" }, status: "COMPLETED" },
      { intent: "PRESS_KEY", target: "settings", params: { key: "enter" }, status: "COMPLETED" },
    ],
  });
  const [health, setHealth] = useState({ status: "HEALTHY" });
  const [isExpanded, setIsExpanded] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMicMuted, setIsMicMuted] = useState(false);

  useEffect(() => {
    // Initial health check
    IRISApiClient.getHealth().then((h) => setHealth(h));

    // Connect WebSocket stream
    const wsClient = new IRISWebSocketClient((event) => {
      if (event.event_type === "IntentParsedEvent") {
        setVoiceState("THINKING");
        setCurrentCommand(event.raw_transcript);
      } else if (event.event_type === "WorkflowStartedEvent") {
        setVoiceState("SPEAKING");
        setActivePlan({
          name: event.plan_name,
          plan_id: event.plan_id,
          steps: event.steps.map((s) => ({ ...s, status: "PENDING" })),
        });
      } else if (event.event_type === "WorkflowStepCompletedEvent") {
        setActivePlan((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            steps: prev.steps.map((s, idx) => (idx === event.step_index ? { ...s, status: "COMPLETED" } : s)),
          };
        });
      }
    });

    wsClient.connect();
    return () => wsClient.disconnect();
  }, []);

  const handleSendTextCommand = async (cmdText) => {
    setCurrentCommand(cmdText);
    setVoiceState("THINKING");

    const newHistoryItem = {
      source: "TEXT",
      timestamp: new Date().toLocaleTimeString(),
      transcript: cmdText,
      intent: cmdText.toLowerCase().includes("settings") ? "BROWSER_SEARCH" : "COMMAND",
      response: "Executing command via BrainOrchestrator...",
    };

    setHistory((prev) => [newHistoryItem, ...prev]);
    const res = await IRISApiClient.executeCommand(cmdText);

    setVoiceState("IDLE");
    if (res.success) {
      newHistoryItem.response = res.message || "Command executed successfully.";
    }
  };

  return (
    <div className={styles.dashboardLayout}>
      <FloatingAssistant
        voiceState={voiceState}
        activeApp={activeApp}
        currentCommand={currentCommand}
        isExpanded={isExpanded}
        onToggleExpand={() => setIsExpanded(!isExpanded)}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      <header className={styles.topHeader}>
        <div className={styles.brandTitle}>
          <span className={styles.eyeIcon}>👁</span>
          <h1>IRIS AI V3</h1>
          <span className={styles.versionBadge}>Desktop Baseline</span>
        </div>
        <SystemTray
          isMicMuted={isMicMuted}
          onToggleMute={() => setIsMicMuted(!isMicMuted)}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onRestartBackend={() => IRISApiClient.getHealth()}
        />
      </header>

      <main className={styles.mainGrid}>
        <section className={styles.leftCol}>
          <ConversationPanel history={history} onSendTextCommand={handleSendTextCommand} />
        </section>

        <section className={styles.rightCol}>
          <WorkflowViewer activePlan={activePlan} />
          <RuntimeDashboard health={health} skillsCount={2} />
        </section>
      </main>

      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </div>
  );
}
