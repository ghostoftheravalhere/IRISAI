# IRIS AI V2.4 — Future Scope & Architectural Vision

## V2.4 Submission Scope & Scope Decisions

For the IBM SkillsBuild Hackathon V2.4 submission, IRIS AI operates in **Visual Feedback Mode**:

- **Voice Input**: **ENABLED** (Microphone capture, VAD, Faster-Whisper offline transcription, intent parsing, action execution).
- **Visual Response Feedback**: **ENABLED** (Commands, intent classification, action execution, workflow plans, and assistant responses display instantly in the UI, System Tray, and Command Log).
- **Eye Tracking & Blink Control**: **ENABLED** (MediaPipe gaze estimation, eye calibration, blink detection, cursor control).
- **Spoken Voice Output (TTS)**: **INTENTIONALLY DISABLED BY CONFIGURATION** (`VOICE_OUTPUT_ENABLED = False`).

> [!NOTE]
> Two-way conversational voice interaction with spoken IRIS responses is planned as a future enhancement. The current V2.4 submission intentionally uses voice input with visual response feedback to maximize system stability and prevent audio feedback/self-hearing during live demonstration.

---

## Restoring Two-Way Conversational Voice

The TTS architecture (including `SpeechOutputManager`, Windows SAPI5 integration, and event dispatch) is fully retained in the codebase.

To restore spoken voice output in post-submission builds:
1. Update `backend/core/config/settings.py` or `.env`:
   ```env
   VOICE_OUTPUT_ENABLED=true
   ```
2. The `SpeechOutputManager` will automatically resume native SAPI5 audio synthesis for assistant responses.
