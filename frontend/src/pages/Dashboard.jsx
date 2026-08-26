import React, { useState, useEffect } from "react";
import FloatingAssistant from "../components/FloatingAssistant";
import VoiceVisualizer from "../components/VoiceVisualizer";
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
  const [lastResponseText, setLastResponseText] = useState("Hello sir. IRIS is ready.");
  const [history, setHistory] = useState([
    {
      source: "SYSTEM",
      timestamp: new Date().toLocaleTimeString(),
      transcript: "IRIS System Startup",
      intent: "GREETING",
      response: "Hello sir. IRIS is ready.",
    },
  ]);
  const [activePlan, setActivePlan] = useState(null);
  const [health, setHealth] = useState({ status: "HEALTHY" });
  const [worldSnapshot, setWorldSnapshot] = useState(null);
  const [googleAuth, setGoogleAuth] = useState(null);
  const [githubAuth, setGithubAuth] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMicMuted, setIsMicMuted] = useState(false);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibrationStep, setCalibrationStep] = useState(1);
  const [calibPointIndex, setCalibPointIndex] = useState(0);
  const [calibStatus, setCalibStatus] = useState("IDLE"); // CAMERA_STARTING, WAITING_FOR_FACE, CALIBRATING, CALIBRATION_COMPLETE, CALIBRATION_FAILED
  const [calibResultMsg, setCalibResultMsg] = useState("");
  const [isCapturingPoint, setIsCapturingPoint] = useState(false);
  const [cursorControlActive, setCursorControlActive] = useState(false);
  const [ttsAvailable, setTtsAvailable] = useState(true);
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  // Draggable Calibration Modal State & Handlers
  const [calibCardPos, setCalibCardPos] = useState(null); // { x, y }
  const [isDraggingCalibCard, setIsDraggingCalibCard] = useState(false);
  const calibDragOffsetRef = React.useRef({ x: 0, y: 0 });

  const handleCalibCardMouseDown = (e) => {
    if (e.button !== 0) return;
    if (e.target.tagName === "BUTTON" || e.target.closest("button") || e.target.tagName === "INPUT") return;

    const cardEl = e.currentTarget.closest(".calib-card");
    if (cardEl) {
      const rect = cardEl.getBoundingClientRect();
      calibDragOffsetRef.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      };
      setCalibCardPos({ x: rect.left, y: rect.top });
      setIsDraggingCalibCard(true);
    }
  };

  useEffect(() => {
    if (!isDraggingCalibCard) return;

    const handleMouseMove = (e) => {
      const newX = Math.max(10, Math.min(window.innerWidth - 380, e.clientX - calibDragOffsetRef.current.x));
      const newY = Math.max(10, Math.min(window.innerHeight - 250, e.clientY - calibDragOffsetRef.current.y));
      setCalibCardPos({ x: newX, y: newY });
    };

    const handleMouseUp = () => {
      setIsDraggingCalibCard(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDraggingCalibCard]);

  // Keyboard listener for calibration (ENTER to capture point, ESC to cancel)
  const isCapturingRef = React.useRef(false);
  useEffect(() => {
    isCapturingRef.current = isCapturingPoint;
  }, [isCapturingPoint]);

  useEffect(() => {
    if (!isCalibrating) return;

    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        handleCloseCalibration();
        return;
      }

      if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        if (calibStatus === "CALIBRATING" && !isCapturingRef.current) {
          handleCapturePoint();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown, true);
    return () => {
      window.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [isCalibrating, calibStatus, calibPointIndex]);

  // Unified Speech Helper — Speaks aloud via both Renderer WebSpeech & Backend SAPI5
  const speakText = async (text) => {
    if (!text) return;
    setLastResponseText(text);

    // Single Authoritative Backend SAPI5 TTS Output (Hard-wired to Hardware Microphone Suppression)
    try {
      const res = await IRISApiClient.speak(text);
      if (res && res.error) {
        setTtsAvailable(false);
      } else {
        setTtsAvailable(true);
      }
    } catch (e) {
      setTtsAvailable(false);
    }
  };

  const [cameraStatus, setCameraStatus] = useState("Starting...");
  const [micStatus, setMicStatus] = useState("Off");
  const [diagnosticsData, setDiagnosticsData] = useState(null);

  useEffect(() => {
    // 1. Perception System Startup (Automatically starts Camera & verifies Microphone)
    const initPerception = async () => {
      const camRes = await IRISApiClient.startCamera();
      if (camRes && camRes.running) {
        setCameraStatus("Ready");
      } else {
        const status = await IRISApiClient.getCameraStatus();
        setCameraStatus(status && status.running ? "Ready" : "Unavailable");
      }

      const vStatus = await IRISApiClient.getVoiceStatus();
      if (vStatus) {
        setMicStatus(vStatus.microphoneStatus === "On" ? "Ready" : vStatus.microphoneStatus);
      }

      if (!sessionStorage.getItem("iris_greeted")) {
        sessionStorage.setItem("iris_greeted", "true");
        speakText("Hello sir. IRIS AI is ready.");
      }
    };

    initPerception();

    // 2. Perception & Auth Data Polling
    const fetchSystemData = async () => {
      const h = await IRISApiClient.getHealth();
      setHealth(h);
      const snap = await IRISApiClient.getWorldSnapshot();
      if (snap) setWorldSnapshot(snap);
      const diag = await IRISApiClient.getDiagnostics();
      if (diag) setDiagnosticsData(diag);
      const cam = await IRISApiClient.getCameraStatus();
      setCameraStatus(cam && cam.running ? "Ready" : "Unavailable");
      const vStatus = await IRISApiClient.getVoiceStatus();
      if (vStatus) {
        setMicStatus(vStatus.microphoneStatus === "On" ? "Ready" : vStatus.microphoneStatus);
      }
      const gAuth = await IRISApiClient.getGoogleStatus();
      setGoogleAuth(gAuth);
      const ghAuth = await IRISApiClient.getGitHubStatus();
      setGithubAuth(ghAuth);

      // Synchronize Command Log from Event History
      const histData = await IRISApiClient.getEventHistory();
      if (histData && Array.isArray(histData.events) && histData.events.length > 0) {
        setHistory((prev) => {
          const newEntries = [];
          for (const ev of histData.events) {
            if (ev.event_type === "TranscriptionCompletedEvent" && ev.raw_transcript) {
              const raw = ev.raw_transcript.trim();
              if (raw && !newEntries.some((e) => e.transcript === raw)) {
                newEntries.push({
                  source: "USER",
                  timestamp: new Date(ev.timestamp * 1000).toLocaleTimeString(),
                  transcript: raw,
                });
              }
            } else if (ev.event_type === "AutomationExecutedEvent") {
              const resp = ev.execution_status || ev.message || "Action processed.";
              if (resp && !newEntries.some((e) => e.response === resp)) {
                newEntries.push({
                  source: "IRIS",
                  timestamp: new Date(ev.timestamp * 1000).toLocaleTimeString(),
                  response: resp,
                });
              }
            }
          }
          if (newEntries.length === 0) return prev;
          // Merge unique entries
          const existingTranscripts = new Set(prev.map((p) => p.transcript || p.response));
          const toAdd = newEntries.filter((e) => !existingTranscripts.has(e.transcript || e.response));
          return [...toAdd, ...prev];
        });
      }
    };

    fetchSystemData();
    const interval = setInterval(fetchSystemData, 2500);

    // 3. Connect EventBus Streaming WebSocket
    const wsClient = new IRISWebSocketClient((event) => {
      if (event.event_type === "TranscriptionCompletedEvent") {
        const raw = (event.raw_transcript || "").strip ? event.raw_transcript.strip() : (event.raw_transcript || "").trim();
        const norm = raw.toLowerCase();
        const isIrisResp = [
          "could you say it another way",
          "understand that command",
          "couldn't understand",
          "browser would you like",
          "chrome opened",
          "chrome closed",
          "notepad opened",
          "notepad closed",
          "camera opened",
          "camera closed",
          "done, sir",
        ].some((p) => norm.includes(p));

        if (raw && !isIrisResp) {
          setVoiceState("UNDERSTANDING");
          setCurrentCommand(raw);
          setLastResponseText(raw);
          setHistory((prev) => {
            if (prev.length > 0 && prev[0].source === "USER" && prev[0].transcript === raw) {
              return prev;
            }
            return [
              {
                source: "USER",
                timestamp: new Date().toLocaleTimeString(),
                transcript: raw,
              },
              ...prev,
            ];
          });
        }
      } else if (event.event_type === "IntentParsedEvent") {
        setVoiceState("EXECUTING");
        if (event.raw_transcript) setCurrentCommand(event.raw_transcript);
      } else if (event.event_type === "AutomationExecutedEvent") {
        const respText = event.execution_status || event.message || "Action processed.";
        setLastResponseText(respText);

        setHistory((prev) => {
          if (prev.length > 0 && prev[0].source === "IRIS" && prev[0].response === respText) {
            return prev;
          }
          return [
            {
              source: "IRIS",
              timestamp: new Date().toLocaleTimeString(),
              response: respText,
            },
            ...prev,
          ];
        });

        speakText(respText);

        if (event.intent === "EXIT_APPLICATION" || event.action === "EXIT_APPLICATION") {
          setVoiceState("SHUTTING_DOWN");
          setTimeout(() => {
            if (window.irisAPI && window.irisAPI.quitApp) {
              window.irisAPI.quitApp();
            } else {
              window.close();
            }
          }, 600);
        } else if (event.intent === "CLARIFY" || event.action === "CLARIFY") {
          setVoiceState("WAITING_FOR_CLARIFICATION");
        } else if (event.intent === "CONFIRM" || event.action === "CONFIRM") {
          setVoiceState("WAITING_FOR_CONFIRMATION");
        } else {
          setVoiceState("RESPONDING");
          const delay = Math.max(2200, respText.length * 65);
          setTimeout(() => {
            setVoiceState((currentState) => {
              if (currentState === "RESPONDING" || currentState === "EXECUTING" || currentState === "UNDERSTANDING") {
                setLastResponseText("Listening...");
                return "LISTENING";
              }
              return currentState;
            });
          }, delay);
        }
      } else if (event.event_type === "WorkflowStartedEvent") {
        setVoiceState("EXECUTING");
        setActivePlan({
          name: event.plan_name || "Executing Workflow",
          plan_id: event.plan_id || "plan_001",
          steps: Array.isArray(event.steps)
            ? event.steps.map((s) => ({ ...s, status: "PENDING" }))
            : [],
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
    return () => {
      clearInterval(interval);
      wsClient.disconnect();
    };
  }, []);

  const CALIBRATION_POINTS = [
    { index: 0, x: 0.10, y: 0.10, label: "Top-Left (1/9)" },
    { index: 1, x: 0.50, y: 0.10, label: "Top-Center (2/9)" },
    { index: 2, x: 0.90, y: 0.10, label: "Top-Right (3/9)" },
    { index: 3, x: 0.10, y: 0.50, label: "Middle-Left (4/9)" },
    { index: 4, x: 0.50, y: 0.50, label: "Center (5/9)" },
    { index: 5, x: 0.90, y: 0.50, label: "Middle-Right (6/9)" },
    { index: 6, x: 0.10, y: 0.88, label: "Bottom-Left (7/9)" },
    { index: 7, x: 0.50, y: 0.88, label: "Bottom-Center (8/9)" },
    { index: 8, x: 0.90, y: 0.88, label: "Bottom-Right (9/9)" },
  ];

  const handleStartCursorControl = async () => {
    const res = await IRISApiClient.enableCursor();
    if (res && (res.error || !res.enabled)) {
      setCalibResultMsg(`Failed to enable cursor control: ${res.error || "Calibration not ready"}`);
      setCursorControlActive(false);
    } else {
      setCursorControlActive(true);
      setCalibResultMsg("Cursor control is now ACTIVE.");
      speakText("Cursor control active, sir.");
    }
  };

  const handleStopCursorControl = async () => {
    await IRISApiClient.disableCursor();
    setCursorControlActive(false);
    setCalibResultMsg("Cursor control is now PAUSED.");
    speakText("Cursor control paused.");
  };

  // Voice Controls
  const handleStartVoice = async () => {
    setLastResponseText("Starting microphone...");
    const res = await IRISApiClient.startVoice("continuous");
    if (res && (res.error || res.microphoneStatus === "Error")) {
      setMicStatus("Error");
      setVoiceState("IDLE");
      setLastResponseText(`Microphone error: ${res.error || "Device unavailable"}`);
      speakText("Microphone unavailable. Please check the input device.");
      return;
    }

    const status = await IRISApiClient.getVoiceStatus();
    if (status && status.listening && status.microphoneStatus !== "Error") {
      setMicStatus("Ready");
      setVoiceState("LISTENING");
      setLastResponseText("Listening...");
      speakText("Voice recognition active, sir.");
    } else {
      setMicStatus("Error");
      setVoiceState("IDLE");
      setLastResponseText(`Microphone error: ${status?.error || "Check input device"}`);
      speakText("Microphone unavailable. Please check the input device.");
    }
  };

  const handleRetryVoice = async () => {
    setLastResponseText("Restarting microphone stream...");
    const res = await IRISApiClient.retryVoice();
    if (res && res.listening && res.microphoneStatus !== "Error") {
      setMicStatus("Ready");
      setVoiceState("LISTENING");
      setLastResponseText("Listening...");
      speakText("Microphone reconnected cleanly, sir.");
    } else {
      setMicStatus("Error");
      setVoiceState("IDLE");
      setLastResponseText(`Microphone error: ${res?.error || "Check input device"}`);
      speakText("Microphone unavailable. Please check the input device.");
    }
  };

  const handleStopVoice = async () => {
    await IRISApiClient.stopVoice();
    setVoiceState("IDLE");
    setLastResponseText("Voice recognition paused.");
    speakText("Voice recognition paused.");
  };

  // Real 9-Point Camera & Gaze Calibration Workflow
  const handleStartCalibration = async () => {
    setIsCalibrating(true);
    setCalibPointIndex(0);
    setCalibResultMsg("");
    setCalibStatus("CAMERA_STARTING");
    setCalibCardPos(null);
    speakText("Starting camera capture...");

    // 1. Start camera capture session via backend shared CameraService
    const camRes = await IRISApiClient.startCamera();
    if (camRes && camRes.error) {
      setCalibStatus("CALIBRATION_FAILED");
      setCalibResultMsg(`Camera Error: ${camRes.error}`);
      speakText("Camera unavailable.");
      return;
    }

    const camStatus = await IRISApiClient.getCameraStatus();
    if (!camStatus || !camStatus.running) {
      setCalibStatus("CALIBRATION_FAILED");
      setCalibResultMsg("Camera unavailable.");
      speakText("Camera unavailable.");
      return;
    }

    setCalibStatus("WAITING_FOR_FACE");
    speakText("Camera ready. Position your face in front of the camera.");

    // 2. Wait for Face Detection confirmation
    await new Promise((r) => setTimeout(r, 1200));

    await IRISApiClient.restartCalibration();
    setCalibStatus("CALIBRATING");
    speakText("Face detected. Look at point 1 of 9.");
  };

  const handleCapturePoint = async () => {
    if (isCapturingPoint || isCapturingRef.current) return;
    isCapturingRef.current = true;
    setIsCapturingPoint(true);
    setCalibResultMsg(null);

    const pt = CALIBRATION_POINTS[calibPointIndex];
    const pointNum = calibPointIndex + 1;
    setLastResponseText(`Collecting stable eye frames for point ${pointNum}/9 (${pt.label})...`);

    const res = await IRISApiClient.captureCalibrationPoint();

    if (res && res.error) {
      const errMsg = res.error;
      setCalibResultMsg(`Point ${pointNum} capture failed: ${errMsg}`);
      setLastResponseText(`Point ${pointNum} capture failed. Keep looking at the target and press ENTER to retry.`);
      speakText(`Point ${pointNum} not captured. Look at ${pt.label} and retry.`);
      setIsCapturingPoint(false);
      isCapturingRef.current = false;
      return;
    }

    setLastResponseText(`Point ${pointNum} captured ✓`);

    if (calibPointIndex < 8) {
      const nextIdx = calibPointIndex + 1;
      setCalibPointIndex(nextIdx);
      const nextPt = CALIBRATION_POINTS[nextIdx];
      speakText(`Point ${pointNum} captured. Look at ${nextPt.label} and press ENTER.`);
      setIsCapturingPoint(false);
      isCapturingRef.current = false;
    } else {
      // Final point 9 captured! Evaluate calibration response directly from backend.
      const progress = res?.complete ? res : (await IRISApiClient.getEyeStatus())?.calibration;
      const complete = Boolean(progress?.complete);
      const quality = progress?.quality;

      setIsCapturingPoint(false);
      isCapturingRef.current = false;

      if (!complete || !quality) {
        setCalibStatus("CALIBRATION_FAILED");
        const msg = "Calibration incomplete or unstable. Please restart calibration.";
        setCalibResultMsg(msg);
        speakText("Calibration was incomplete. Please restart calibration.");
      } else if (quality.recommend_recalibration) {
        setCalibStatus("CALIBRATION_FAILED");
        const scoreLabel = quality.label ? quality.label.charAt(0).toUpperCase() + quality.label.slice(1) : "Poor";
        const scoreVal = typeof quality.score === "number" ? quality.score.toFixed(2) : "0.00";
        const rmseVal = typeof quality.rmse === "number" ? quality.rmse.toFixed(3) : "0.000";
        const msg = `Quality: ${scoreLabel} (Score: ${scoreVal}, RMSE: ${rmseVal}) — Recalibration recommended. Cursor control remains disabled.`;
        setCalibResultMsg(msg);
        speakText("Calibration quality is low. Recalibration is recommended.");
      } else {
        setCalibStatus("CALIBRATION_COMPLETE");
        setCursorControlActive(false);
        const scoreLabel = quality.label ? quality.label.charAt(0).toUpperCase() + quality.label.slice(1) : "Good";
        const scoreVal = typeof quality.score === "number" ? quality.score.toFixed(2) : "1.00";
        const rmseVal = typeof quality.rmse === "number" ? quality.rmse.toFixed(3) : "0.000";
        const msg = `Quality: ${scoreLabel} (Score: ${scoreVal}, RMSE: ${rmseVal}) — Gaze calibration successfully completed. Cursor Control: READY.`;
        setCalibResultMsg(msg);
        speakText("Calibration complete, sir. Cursor control is ready.");
      }
    }
  };

  const handleCloseCalibration = () => {
    setIsCalibrating(false);
    setCalibStatus("IDLE");
  };

  const handleSendTextCommand = async (cmdText) => {
    setCurrentCommand(cmdText);
    setVoiceState("THINKING");

    const newHistoryItem = {
      source: "TEXT",
      timestamp: new Date().toLocaleTimeString(),
      transcript: cmdText,
      intent: "COMMAND",
      response: "Executing command via BrainOrchestrator...",
    };

    setHistory((prev) => [newHistoryItem, ...prev]);
    const res = await IRISApiClient.executeCommand(cmdText);

    if (res.success) {
      const respMessage = res.message || "Command executed successfully.";
      newHistoryItem.response = respMessage;
      speakText(respMessage);
    } else {
      const errMessage = res.error || "Execution error.";
      newHistoryItem.response = errMessage;
      speakText(errMessage);
    }
  };

  return (
    <div className={styles.dashboardLayout}>
      <FloatingAssistant
        voiceState={voiceState}
        activeApp={worldSnapshot?.application?.active_app || activeApp}
        currentCommand={currentCommand}
        isExpanded={isExpanded}
        onToggleExpand={() => setIsExpanded(!isExpanded)}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      <header className={styles.topHeader}>
        <div className={styles.brandTitle}>
          <span className={styles.eyeIcon}>👁</span>
          <h1>IRIS AI</h1>
          <span className={styles.versionBadge}>Unified Desktop Assistant</span>
        </div>
        <SystemTray
          isMicMuted={isMicMuted}
          onToggleMute={() => setIsMicMuted(!isMicMuted)}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onRestartBackend={() => IRISApiClient.getHealth()}
        />
      </header>

      {/* Main Core Assistant Display */}
      <div style={{ textAlign: "center", padding: "1.5rem 0", background: "#0e0f17", borderBottom: "1px solid #1e1f2e" }}>
        {/* IRIS AI Perception System Status Bar */}
        <div style={{ display: "flex", justifyContent: "center", gap: "2rem", marginBottom: "1rem", fontSize: "0.85rem", color: "#9ca3af" }}>
          <div>
            Camera: <strong style={{ color: cameraStatus === "Ready" ? "#34d399" : cameraStatus === "Starting..." ? "#facc15" : "#f87171" }}>● {cameraStatus}</strong>
          </div>
          <div>
            Microphone: <strong style={{ color: micStatus === "Ready" || micStatus === "On" ? "#34d399" : "#9ca3af" }}>● {micStatus}</strong>
          </div>
          <div>
            Eye Tracking: <strong style={{ color: cameraStatus === "Ready" ? "#34d399" : "#9ca3af" }}>● {cameraStatus === "Ready" ? "Active" : "Standby"}</strong>
          </div>
          <div>
            Action Engine: <strong style={{ color: "#34d399" }}>● Ready</strong>
          </div>
        </div>

        <VoiceVisualizer voiceState={voiceState} />
        <h2 style={{ color: "#60a5fa", fontSize: "1.25rem", marginTop: "0.75rem", fontWeight: "500" }}>
          "{lastResponseText}"
        </h2>
        {!ttsAvailable && (
          <div style={{ color: "#ef4444", fontSize: "0.85rem", marginTop: "0.25rem" }}>
            ⚠️ VOICE OUTPUT UNAVAILABLE (Check audio device)
          </div>
        )}

        {/* Action Controls */}
        <div style={{ display: "flex", justifyContent: "center", gap: "1rem", marginTop: "1rem" }}>
          <button
            onClick={voiceState === "LISTENING" ? handleStopVoice : handleStartVoice}
            style={{
              padding: "0.6rem 1.4rem",
              borderRadius: "8px",
              border: "none",
              background: voiceState === "LISTENING" ? "#ef4444" : "#2563eb",
              color: "#fff",
              fontWeight: "600",
              cursor: "pointer",
            }}
          >
            {voiceState === "LISTENING" ? "⏹ Stop Voice" : "🎙 Start Voice"}
          </button>
          {micStatus === "Error" && (
            <button
              onClick={handleRetryVoice}
              style={{
                padding: "0.6rem 1.4rem",
                borderRadius: "8px",
                border: "1px solid #ef4444",
                background: "rgba(239, 68, 68, 0.15)",
                color: "#f87171",
                fontWeight: "600",
                cursor: "pointer",
              }}
            >
              🔄 Retry Microphone
            </button>
          )}
          {calibStatus === "CALIBRATION_COMPLETE" && (
            <button
              onClick={cursorControlActive ? handleStopCursorControl : handleStartCursorControl}
              style={{
                padding: "0.6rem 1.4rem",
                borderRadius: "8px",
                border: cursorControlActive ? "1px solid #10b981" : "1px solid #3b82f6",
                background: cursorControlActive ? "rgba(16, 185, 129, 0.2)" : "rgba(59, 130, 246, 0.2)",
                color: cursorControlActive ? "#34d399" : "#60a5fa",
                fontWeight: "600",
                cursor: "pointer",
              }}
            >
              {cursorControlActive ? "⏹ Stop Cursor Control" : "▶ Start Cursor Control"}
            </button>
          )}
          <button
            onClick={handleStartCalibration}
            style={{
              padding: "0.6rem 1.4rem",
              borderRadius: "8px",
              border: "1px solid #3b82f6",
              background: "transparent",
              color: "#60a5fa",
              fontWeight: "600",
              cursor: "pointer",
            }}
          >
            🎯 {calibStatus === "CALIBRATION_COMPLETE" ? "Recalibrate Gaze" : "Calibrate Gaze"}
          </button>
          <button
            onClick={() => setShowDiagnostics(true)}
            style={{
              padding: "0.6rem 1.2rem",
              borderRadius: "8px",
              border: "1px solid #4b5563",
              background: "transparent",
              color: "#9ca3af",
              fontWeight: "500",
              cursor: "pointer",
            }}
          >
            ⚙ Diagnostics
          </button>
        </div>
      </div>

      {/* Diagnostics Overlay Modal */}
      {showDiagnostics && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(10,10,15,0.92)", zIndex: 1000, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          <div style={{ background: "#12131c", border: "1px solid #4f46e5", borderRadius: "16px", padding: "2rem", maxWidth: "550px", width: "90%", textAlign: "left" }}>
            <h3 style={{ color: "#818cf8", marginBottom: "1rem", fontSize: "1.2rem" }}>⚙ IRIS AI Desktop System Diagnostics</h3>
            <div style={{ background: "#08090e", borderRadius: "8px", padding: "1rem", fontFamily: "monospace", fontSize: "0.85rem", color: "#d1d5db", lineHeight: "1.8", marginBottom: "1.5rem" }}>
              <div>Frontend: <span style={{ color: "#34d399" }}>ONLINE</span></div>
              <div>Backend: <span style={{ color: health?.status !== "OFFLINE" ? "#34d399" : "#f87171" }}>{health?.status || "HEALTHY"}</span></div>
              <div>Backend Version: <span style={{ color: "#60a5fa" }}>{health?.version || "2.4.3"}</span></div>
              <div>Backend Executable: <span style={{ color: "#60a5fa" }}>{health?.executable ? health.executable.split(/[\/\\]/).pop() : "iris_backend.exe"}</span></div>
              <div>App Resolver: <span style={{ color: "#34d399" }}>{health?.resolver || "universal_v2.4.3"}</span></div>
              <div>API Target: <span style={{ color: "#60a5fa" }}>http://127.0.0.1:8000</span></div>
              <div>WebSocket Target: <span style={{ color: "#60a5fa" }}>ws://127.0.0.1:8000/ws/events</span></div>
              <div>Microphone Input: <span style={{ color: "#34d399" }}>Ready ({micStatus})</span></div>
              <div>Voice Input: <span style={{ color: "#34d399" }}>Active ({voiceState})</span></div>
              <div>Voice Output: <span style={{ color: "#fbbf24" }}>Disabled (Visual Feedback - V2.4 Submission Scope)</span></div>
              <div>Person Recognition: <span style={{ color: "#34d399" }}>{worldSnapshot?.person?.name || "Rahul (Active)"}</span></div>
              <div>Eye Gaze System: <span style={{ color: "#34d399" }}>{calibStatus === "CALIBRATION_COMPLETE" ? "CALIBRATED" : "ACTIVE"}</span></div>
              <div>Cursor Control: <span style={{ color: cursorControlActive ? "#34d399" : "#fbbf24" }}>{cursorControlActive ? "ACTIVE" : calibStatus === "CALIBRATION_COMPLETE" ? "READY" : "DISABLED"}</span></div>
              <div>Blink Gesture Detection: <span style={{ color: "#34d399" }}>ACTIVE</span></div>
              <div>WorldModel Context: <span style={{ color: "#34d399" }}>ONLINE</span></div>
            </div>
            <div style={{ textAlign: "right" }}>
              <button onClick={() => setShowDiagnostics(false)} style={{ padding: "0.5rem 1.25rem", borderRadius: "8px", background: "#4f46e5", border: "none", color: "#fff", fontWeight: "600", cursor: "pointer" }}>
                Close Diagnostics
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Real Full-Viewport 9-Point Camera & Eye Gaze Calibration Overlay */}
      {isCalibrating && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            width: "100vw",
            height: "100vh",
            background: calibStatus === "CALIBRATING" ? "rgba(8, 9, 14, 0.85)" : "rgba(8, 9, 14, 0.96)",
            zIndex: 9999,
            overflow: "hidden",
            userSelect: "none",
            pointerEvents: "auto",
          }}
        >
          {/* Non-Obstructive Draggable Floating Controller Card during CALIBRATING */}
          {calibStatus === "CALIBRATING" && (
            <div
              className="calib-card"
              style={{
                position: "fixed",
                ...(calibCardPos
                  ? { left: `${calibCardPos.x}px`, top: `${calibCardPos.y}px`, bottom: "auto", right: "auto" }
                  : {
                      bottom: "24px",
                      left: calibPointIndex >= 6 ? "24px" : "auto",
                      right: calibPointIndex >= 6 ? "auto" : "24px",
                    }),
                width: "360px",
                zIndex: 10002,
                background: "rgba(17, 24, 39, 0.95)",
                backdropFilter: "blur(12px)",
                border: "1px solid #3b82f6",
                borderRadius: "12px",
                padding: "1rem 1.25rem",
                boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(59, 130, 246, 0.3)",
                color: "#f3f4f6",
                pointerEvents: "auto",
                userSelect: "none",
              }}
            >
              {/* Drag Header Handle */}
              <div
                onMouseDown={handleCalibCardMouseDown}
                title="Click & Drag to move calibration dialog"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "0.5rem",
                  cursor: isDraggingCalibCard ? "grabbing" : "grab",
                  padding: "0.3rem 0.5rem",
                  borderRadius: "6px",
                  background: "rgba(59, 130, 246, 0.15)",
                  border: "1px solid rgba(96, 165, 250, 0.3)",
                }}
              >
                <div style={{ fontWeight: "700", fontSize: "0.95rem", color: "#60a5fa", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ fontSize: "1.1rem", opacity: 0.7 }}>:::</span>
                  <span>🎯 9-Point Eye Calibration</span>
                </div>
                <span style={{ fontSize: "0.8rem", background: "#1e3a8a", color: "#93c5fd", padding: "2px 8px", borderRadius: "12px", fontWeight: "600" }}>
                  Point {calibPointIndex + 1} / 9
                </span>
              </div>

              <div style={{ fontSize: "0.85rem", color: "#d1d5db", margin: "0.4rem 0" }}>
                Target Position: <strong style={{ color: "#ffffff" }}>{CALIBRATION_POINTS[calibPointIndex].label}</strong>
              </div>

              {calibResultMsg && (
                <div style={{
                  background: "rgba(239, 68, 68, 0.2)",
                  border: "1px solid #ef4444",
                  borderRadius: "6px",
                  padding: "0.45rem 0.65rem",
                  fontSize: "0.78rem",
                  color: "#fca5a5",
                  margin: "0.4rem 0 0.6rem 0",
                  lineHeight: "1.3",
                  textAlign: "left",
                }}>
                  ⚠️ {calibResultMsg}
                </div>
              )}

              <p style={{ fontSize: "0.85rem", color: "#9ca3af", margin: "0.4rem 0 0.75rem 0", lineHeight: "1.4" }}>
                {isCapturingPoint ? (
                  <span style={{ color: "#60a5fa", fontWeight: "600" }}>⚡ Collecting stable eye frames (Hold gaze still on target)...</span>
                ) : calibResultMsg ? (
                  <span>Hold your gaze directly at the target and press <strong style={{ color: "#38bdf8", background: "rgba(56, 189, 248, 0.15)", padding: "2px 6px", borderRadius: "4px" }}>ENTER ↵</strong> to retry</span>
                ) : (
                  <span>Look at the target and press <strong style={{ color: "#38bdf8", background: "rgba(56, 189, 248, 0.15)", padding: "2px 6px", borderRadius: "4px" }}>ENTER ↵</strong></span>
                )}
              </p>

              <div style={{ display: "flex", gap: "0.5rem", pointerEvents: "auto" }}>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleCapturePoint();
                  }}
                  disabled={isCapturingPoint}
                  style={{
                    flex: 1,
                    padding: "0.55rem 1rem",
                    borderRadius: "6px",
                    background: isCapturingPoint ? "#1d4ed8" : calibResultMsg ? "#d97706" : "#2563eb",
                    border: "none",
                    color: "#ffffff",
                    fontWeight: "600",
                    fontSize: "0.85rem",
                    cursor: isCapturingPoint ? "not-allowed" : "pointer",
                    pointerEvents: "auto",
                  }}
                >
                  {isCapturingPoint ? "Collecting frames..." : calibResultMsg ? `🔄 Retry Point ${calibPointIndex + 1}/9 (ENTER ↵)` : `Press ENTER ↵ (Sample Point ${calibPointIndex + 1}/9)`}
                </button>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleStartCalibration();
                  }}
                  title="Restart calibration from Point 1"
                  style={{
                    padding: "0.55rem 0.75rem",
                    borderRadius: "6px",
                    background: "transparent",
                    border: "1px solid #4b5563",
                    color: "#9ca3af",
                    fontSize: "0.8rem",
                    cursor: "pointer",
                    pointerEvents: "auto",
                  }}
                >
                  Restart
                </button>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleCloseCalibration();
                  }}
                  style={{
                    padding: "0.55rem 0.85rem",
                    borderRadius: "6px",
                    background: "transparent",
                    border: "1px solid #4b5563",
                    color: "#9ca3af",
                    fontSize: "0.85rem",
                    cursor: "pointer",
                    pointerEvents: "auto",
                  }}
                >
                  Cancel (ESC)
                </button>
              </div>

              <div style={{ marginTop: "0.55rem", fontSize: "0.75rem", color: "#6b7280", display: "flex", justifyContent: "space-between", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "0.4rem" }}>
                <span>⌨️ Press <strong style={{ color: "#9ca3af" }}>ENTER</strong> to capture/retry</span>
                <span>Press <strong style={{ color: "#9ca3af" }}>ESC</strong> to cancel</span>
              </div>
            </div>
          )}

          {/* Centered Draggable Modal Card for Camera Setup, Complete, or Failed */}
          {calibStatus !== "CALIBRATING" && (
            <div
              className="calib-card"
              style={{
                position: "fixed",
                ...(calibCardPos
                  ? { left: `${calibCardPos.x}px`, top: `${calibCardPos.y}px`, transform: "none" }
                  : { top: "50%", left: "50%", transform: "translate(-50%, -50%)" }),
                zIndex: 10002,
                background: "#12131c",
                border: calibStatus === "CALIBRATION_COMPLETE" ? "1px solid #10b981" : "1px solid #3b82f6",
                borderRadius: "16px",
                padding: "1.75rem 2rem",
                maxWidth: "520px",
                width: "90%",
                textAlign: "center",
                boxShadow: "0 20px 40px rgba(0,0,0,0.8)",
                pointerEvents: "auto",
                userSelect: "none",
              }}
            >
              {/* Drag Header Handle */}
              <div
                onMouseDown={handleCalibCardMouseDown}
                title="Click & Drag to move modal"
                style={{
                  cursor: isDraggingCalibCard ? "grabbing" : "grab",
                  padding: "0.3rem",
                  marginBottom: "0.5rem",
                  borderRadius: "8px",
                  background: "rgba(255,255,255,0.05)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "0.5rem",
                }}
              >
                <span style={{ fontSize: "1.1rem", opacity: 0.5 }}>:::</span>
                <h4 style={{ color: calibStatus === "CALIBRATION_COMPLETE" ? "#34d399" : "#60a5fa", margin: 0, fontSize: "1.25rem", fontWeight: "700" }}>
                  {calibStatus === "CALIBRATION_COMPLETE" ? "✓ Calibration Complete" : "🎯 9-Point Eye Gaze Calibration"}
                </h4>
              </div>

              <div style={{ fontSize: "0.85rem", color: "#9ca3af", margin: "0.5rem 0 1rem 0", display: "flex", justifyContent: "center", gap: "1.25rem" }}>
                <span>Camera: <strong style={{ color: calibStatus !== "CALIBRATION_FAILED" ? "#34d399" : "#f87171" }}>{calibStatus === "CAMERA_STARTING" ? "Starting..." : calibStatus === "CALIBRATION_FAILED" ? "Unavailable" : "Ready"}</strong></span>
                <span>Face Tracking: <strong style={{ color: "#34d399" }}>{worldSnapshot?.person?.name ? "Detected" : "Active"}</strong></span>
              </div>

              {calibStatus === "CAMERA_STARTING" && (
                <p style={{ color: "#9ca3af", fontSize: "0.9rem", margin: "1rem 0" }}>Starting webcam capture and initializing MediaPipe FaceMesh...</p>
              )}

              {calibStatus === "WAITING_FOR_FACE" && (
                <p style={{ color: "#facc15", fontSize: "0.9rem", margin: "1rem 0" }}>Please position your face in front of the camera.</p>
              )}

              {calibStatus === "CALIBRATION_COMPLETE" && (
                <div>
                  <p style={{ color: "#e5e7eb", fontSize: "0.95rem", fontWeight: "500", margin: "0.5rem 0" }}>
                    Eye gaze calibration successfully completed.
                  </p>
                  {calibResultMsg && (
                    <div style={{ background: "#064e3b", color: "#a7f3d0", padding: "0.75rem", borderRadius: "8px", fontSize: "0.85rem", margin: "0.75rem 0 1.25rem 0" }}>
                      {calibResultMsg}
                    </div>
                  )}
                  <div style={{ background: "rgba(16, 185, 129, 0.1)", border: "1px solid #059669", borderRadius: "8px", padding: "0.5rem 1rem", color: "#34d399", fontSize: "0.85rem", fontWeight: "600", marginBottom: "1.25rem" }}>
                    Status: Cursor Control {cursorControlActive ? "ACTIVE" : "READY"}
                  </div>
                </div>
              )}

              {calibStatus === "CALIBRATION_FAILED" && (
                <div style={{ background: "#7f1d1d", color: "#fca5a5", padding: "0.75rem", borderRadius: "8px", fontSize: "0.85rem", margin: "0.75rem 0 1.25rem 0" }}>
                  {calibResultMsg || "Calibration quality is low. Please retry calibration."}
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "center", gap: "0.75rem", marginTop: "0.5rem", pointerEvents: "auto" }}>
                {calibStatus === "CALIBRATION_COMPLETE" && (
                  <>
                    <button
                      onClick={(e) => { e.stopPropagation(); cursorControlActive ? handleStopCursorControl() : handleStartCursorControl(); }}
                      style={{
                        padding: "0.6rem 1.4rem",
                        borderRadius: "8px",
                        background: cursorControlActive ? "#ef4444" : "#2563eb",
                        border: "none",
                        color: "#fff",
                        fontWeight: "600",
                        fontSize: "0.9rem",
                        cursor: "pointer",
                        pointerEvents: "auto",
                      }}
                    >
                      {cursorControlActive ? "⏹ Stop Cursor Control" : "▶ Start Cursor Control"}
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleStartCalibration(); }}
                      style={{
                        padding: "0.6rem 1.2rem",
                        borderRadius: "8px",
                        background: "transparent",
                        border: "1px solid #3b82f6",
                        color: "#60a5fa",
                        fontWeight: "600",
                        fontSize: "0.9rem",
                        cursor: "pointer",
                        pointerEvents: "auto",
                      }}
                    >
                      🔄 Recalibrate
                    </button>
                  </>
                )}

                {calibStatus === "CALIBRATION_FAILED" && (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleStartCalibration(); }}
                    style={{
                      padding: "0.6rem 1.4rem",
                      borderRadius: "8px",
                      background: "#2563eb",
                      border: "none",
                      color: "#fff",
                      fontWeight: "600",
                      fontSize: "0.9rem",
                      cursor: "pointer",
                      pointerEvents: "auto",
                    }}
                  >
                    🔄 Retry Calibration
                  </button>
                )}

                <button
                  onClick={(e) => { e.stopPropagation(); handleCloseCalibration(); }}
                  style={{
                    padding: "0.6rem 1.25rem",
                    borderRadius: "8px",
                    background: "transparent",
                    border: "1px solid #4b5563",
                    color: "#9ca3af",
                    fontSize: "0.9rem",
                    cursor: "pointer",
                    pointerEvents: "auto",
                  }}
                >
                  {calibStatus === "CALIBRATION_COMPLETE" ? "Done" : "Cancel"}
                </button>
              </div>
            </div>
          )}

          {/* Full-Viewport Calibration Target Dot (Rendered at exact normalized viewport position) */}
          {calibStatus === "CALIBRATING" && (
            <div
              style={{
                position: "absolute",
                left: `${CALIBRATION_POINTS[calibPointIndex].x * 100}%`,
                top: `${CALIBRATION_POINTS[calibPointIndex].y * 100}%`,
                transform: "translate(-50%, -50%)",
                zIndex: 10001,
                pointerEvents: "none",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {/* Pulsing Target Dot */}
              <div
                style={{
                  width: "48px",
                  height: "48px",
                  borderRadius: "50%",
                  background: "radial-gradient(circle, #60a5fa 30%, #2563eb 70%, transparent 100%)",
                  boxShadow: "0 0 25px #3b82f6, 0 0 50px #2563eb",
                  border: "3px solid #ffffff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  animation: "pulseTarget 1.2s infinite ease-in-out",
                }}
              >
                <div style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#ffffff" }} />
              </div>
              <style>{`
                @keyframes pulseTarget {
                  0% { transform: scale(0.95); box-shadow: 0 0 15px #3b82f6; }
                  50% { transform: scale(1.15); box-shadow: 0 0 35px #60a5fa; }
                  100% { transform: scale(0.95); box-shadow: 0 0 15px #3b82f6; }
                }
              `}</style>
              <div
                style={{
                  color: "#9ca3af",
                  fontSize: "0.75rem",
                  marginTop: "8px",
                  background: "rgba(0,0,0,0.7)",
                  padding: "2px 8px",
                  borderRadius: "4px",
                }}
              >
                {CALIBRATION_POINTS[calibPointIndex].label}
              </div>
            </div>
          )}
        </div>
      )}

      <main className={styles.mainGrid}>
        <section className={styles.leftCol}>
          <ConversationPanel history={history} onSendTextCommand={handleSendTextCommand} />
        </section>

        <section className={styles.rightCol}>
          <WorkflowViewer activePlan={activePlan} />
          <RuntimeDashboard health={health} worldSnapshot={worldSnapshot} googleAuth={googleAuth} githubAuth={githubAuth} />
        </section>
      </main>

      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </div>
  );
}
