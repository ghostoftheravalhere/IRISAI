"""Sprint 3 tests for perception extraction and camera capture ownership."""

from __future__ import annotations

import inspect

from backend.eye_tracking import camera_service as camera_module
from backend.eye_tracking.camera_service import CameraService
from backend.perception.camera import capture_service as capture_module


def test_face_mesh_old_and_new_imports_share_symbols() -> None:
    from backend.eye_tracking import face_mesh_service as old
    from backend.perception.camera import face_mesh_provider as new

    assert old.FaceMeshService is new.FaceMeshService
    assert old.FaceMeshFrameResult is new.FaceMeshFrameResult
    assert old.EyeData is new.EyeData
    assert old.NormalizedLandmark is new.NormalizedLandmark
    assert old.LEFT_EYE_LANDMARK_INDICES == new.LEFT_EYE_LANDMARK_INDICES
    assert old.RIGHT_EYE_LANDMARK_INDICES == new.RIGHT_EYE_LANDMARK_INDICES


def test_camera_service_public_api_signatures_unchanged() -> None:
    expected = {
        "start": "(self) -> 'dict[str, bool | int]'",
        "stop": "(self) -> 'dict[str, bool | int]'",
        "cleanup": "(self) -> 'None'",
        "status": "(self) -> 'dict[str, bool | int]'",
        "mjpeg_frame_stream": "(self) -> 'Iterator[bytes]'",
        "get_latest_eye_data": "(self) -> 'EyeData | None'",
    }

    for name, signature in expected.items():
        assert str(inspect.signature(getattr(CameraService, name))) == signature


def test_camera_service_construct_and_cleanup_do_not_open_capture(monkeypatch) -> None:
    created: list[int] = []

    class FakeVideoCapture:
        def __init__(self, index: int) -> None:
            created.append(index)

    monkeypatch.setattr(capture_module.cv2, "VideoCapture", FakeVideoCapture, raising=False)
    monkeypatch.setattr(camera_module, "FaceMeshService", lambda: _FakeFaceMesh())

    service = CameraService(camera_index=3)
    service.cleanup()

    assert created == []


def test_camera_service_start_status_stop_create_one_video_capture(monkeypatch) -> None:
    created: list[int] = []

    class FakeVideoCapture:
        def __init__(self, index: int) -> None:
            created.append(index)
            self.opened = True
            self.released = False

        def isOpened(self) -> bool:
            return self.opened

        def read(self):
            return False, None

        def release(self) -> None:
            self.released = True
            self.opened = False

    class FakeThread:
        def __init__(self, target, name: str, daemon: bool) -> None:
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            return None

        def is_alive(self) -> bool:
            return False

        def join(self, timeout: float | None = None) -> None:
            return None

    monkeypatch.setattr(capture_module.cv2, "VideoCapture", FakeVideoCapture, raising=False)
    monkeypatch.setattr(camera_module, "FaceMeshService", lambda: _FakeFaceMesh())
    monkeypatch.setattr(camera_module, "Thread", FakeThread)

    service = CameraService(camera_index=7)
    try:
        status = service.start()
        assert status["running"] is True
        assert service.status()["running"] is True
        assert service.status()["connected"] is True
        assert created == [7]

        stopped = service.stop()
        assert stopped["running"] is False
        assert stopped["connected"] is True
        assert created == [7]
    finally:
        service.cleanup()


class _FakeFaceMesh:
    def close(self) -> None:
        return None
