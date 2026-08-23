"""Voice recognition API routes."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.voice.recognizer import ListenMode, VoiceRecognitionState

router = APIRouter(tags=["voice"])


class VoiceStatusResponse(BaseModel):
    """Voice recognition status response."""

    model_config = ConfigDict(extra="forbid")

    microphoneStatus: str
    listening: bool
    listenMode: str
    pushToTalkActive: bool
    latestTranscript: str | None
    detectedIntent: str | None
    executionStatus: str
    error: str | None
    message: str | None = None


class VoiceModeRequest(BaseModel):
    """Request body for switching listen mode."""

    model_config = ConfigDict(extra="forbid")

    mode: str = Field(description="continuous or push_to_talk")


class VoiceStartRequest(BaseModel):
    """Optional start options."""

    model_config = ConfigDict(extra="forbid")

    mode: str | None = Field(default=None, description="continuous or push_to_talk")


def _serialize(state: VoiceRecognitionState, message: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "microphoneStatus": state.microphoneStatus,
        "listening": state.listening,
        "listenMode": state.listenMode,
        "pushToTalkActive": state.pushToTalkActive,
        "latestTranscript": state.latestTranscript,
        "detectedIntent": state.detectedIntent,
        "executionStatus": state.executionStatus,
        "error": state.error,
    }
    if message is not None:
        payload["message"] = message
    return payload


@router.get("/status", response_model=VoiceStatusResponse)
async def voice_status(request: Request) -> dict[str, object]:
    """Return the current voice recognition status."""
    return _serialize(request.app.state.voice.get_state())


@router.post("/start", response_model=VoiceStatusResponse)
async def voice_start(request: Request, body: VoiceStartRequest | None = None) -> dict[str, object]:
    """Start continuous or push-to-talk listening."""
    voice = request.app.state.voice
    mode = body.mode if body is not None else None
    try:
        if mode is not None:
            ListenMode(mode.strip().lower().replace("-", "_"))
        state = voice.start(mode=mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _serialize(state, message="Voice recognition started.")


@router.post("/stop", response_model=VoiceStatusResponse)
async def voice_stop(request: Request) -> dict[str, object]:
    """Stop listening."""
    state = request.app.state.voice.stop()
    return _serialize(state, message="Voice recognition stopped.")


class SpeakRequest(BaseModel):
    """Request body for speaking text via TTS."""

    text: str = Field(description="Text to synthesize and speak aloud")


@router.post("/speak")
async def voice_speak(request: Request, body: SpeakRequest) -> dict[str, object]:
    """Synthesize and speak text output using native TTS engine."""
    speech_mgr = getattr(request.app.state, "speech_output_manager", None)
    if speech_mgr is not None:
        duration = speech_mgr.speak(body.text)
        return {"success": True, "text": body.text, "duration_ms": duration}
    return {"success": False, "error": "Speech manager unattached"}


@router.post("/mode", response_model=VoiceStatusResponse)
async def voice_set_mode(request: Request, body: VoiceModeRequest) -> dict[str, object]:
    """Switch between continuous and push-to-talk modes."""
    try:
        state = request.app.state.voice.set_mode(body.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize(state, message=f"Listen mode set to {state.listenMode}.")


@router.post("/push-to-talk/start", response_model=VoiceStatusResponse)
async def voice_ptt_start(request: Request) -> dict[str, object]:
    """Begin capturing while in push-to-talk mode."""
    state = request.app.state.voice.push_to_talk_start()
    if state.error:
        raise HTTPException(status_code=409, detail=state.error)
    return _serialize(state, message="Push-to-talk started.")


@router.post("/push-to-talk/stop", response_model=VoiceStatusResponse)
async def voice_ptt_stop(request: Request) -> dict[str, object]:
    """Stop capturing in push-to-talk mode."""
    state = request.app.state.voice.push_to_talk_stop()
    return _serialize(state, message="Push-to-talk stopped.")


@router.get("/telemetry")
async def voice_telemetry(request: Request) -> dict[str, object]:
    """Return current voice telemetry metrics and execution history."""
    if not hasattr(request.app.state, "voice_telemetry"):
        raise HTTPException(status_code=503, detail="Voice telemetry service not initialized.")
    return request.app.state.voice_telemetry.get_summary()


@router.get("/diagnostics")
async def voice_diagnostics(request: Request) -> dict[str, object]:
    """Return detailed hardware microphone diagnostic metadata."""
    voice = request.app.state.voice
    if hasattr(voice, "get_diagnostics"):
        return voice.get_diagnostics()
    return {"status": "UNAVAILABLE"}


@router.post("/retry", response_model=VoiceStatusResponse)
async def voice_retry(request: Request) -> dict[str, object]:
    """Safely stop, clear stale streams/buffers, and restart microphone recognition."""
    voice = request.app.state.voice
    voice.stop()
    import time
    time.sleep(0.1)
    state = voice.start()
    return _serialize(state, message="Microphone recognition restarted.")


@router.post("/shutdown")
async def voice_shutdown(request: Request) -> dict[str, object]:
    """Shutdown voice recognition, cancel active/queued TTS, and release audio resources."""
    speech_mgr = getattr(request.app.state, "speech_output_manager", None)
    if speech_mgr is not None and hasattr(speech_mgr, "shutdown"):
        speech_mgr.shutdown()

    voice = request.app.state.voice
    if hasattr(voice, "shutdown"):
        voice.shutdown()

    return {"success": True, "message": "Voice engine shut down cleanly."}
