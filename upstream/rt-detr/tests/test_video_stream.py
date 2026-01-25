"""
Unit tests for video_stream module
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import numpy as np

# Ensure correct path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))


def test_create_stream_reader_accepts_rtsp():
    from app.services.video_stream import create_stream_reader, RTSPStreamReader

    reader = create_stream_reader("rtsp://localhost:8554/camera")

    assert isinstance(reader, RTSPStreamReader)


def test_create_stream_reader_rejects_non_rtsp():
    from app.services.video_stream import create_stream_reader, VideoStreamError

    with pytest.raises(VideoStreamError):
        create_stream_reader("http://example.com/stream")


def test_connect_uses_opencv_capture(monkeypatch):
    from app.services.video_stream import RTSPStreamReader
    import cv2

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    def fake_capture(url, backend):
        assert url == "rtsp://localhost:8554/camera"
        assert backend == cv2.CAP_FFMPEG
        return mock_cap

    monkeypatch.setattr(cv2, "VideoCapture", fake_capture)

    reader = RTSPStreamReader("rtsp://localhost:8554/camera")
    assert reader.connect() is True


def test_get_stream_info_returns_none_when_closed():
    from app.services.video_stream import RTSPStreamReader

    reader = RTSPStreamReader("rtsp://localhost:8554/camera")
    assert reader.get_stream_info() is None

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    reader.cap = mock_cap

    assert reader.get_stream_info() is None


def test_get_stream_info_returns_values():
    from app.services.video_stream import RTSPStreamReader
    import cv2

    reader = RTSPStreamReader("rtsp://localhost:8554/camera")
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.side_effect = [1920.0, 1080.0, 25.0]
    reader.cap = mock_cap

    info = reader.get_stream_info()

    assert info == {"width": 1920, "height": 1080, "fps": 25.0}
    mock_cap.get.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH)
    mock_cap.get.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT)
    mock_cap.get.assert_any_call(cv2.CAP_PROP_FPS)


@pytest.mark.asyncio
async def test_stream_frames_stops_on_max_frames():
    from app.services.video_stream import RTSPStreamReader, VideoFrame

    reader = RTSPStreamReader("rtsp://localhost:8554/camera")
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    reader.read_frame = AsyncMock(side_effect=[
        VideoFrame(frame=frame, timestamp=1.0, frame_index=1, width=10, height=10),
        VideoFrame(frame=frame, timestamp=2.0, frame_index=2, width=10, height=10),
        VideoFrame(frame=frame, timestamp=3.0, frame_index=3, width=10, height=10)
    ])

    frames = []
    async for item in reader.stream_frames(max_frames=2):
        frames.append(item)

    assert len(frames) == 2
    assert reader.running is True


@pytest.mark.asyncio
async def test_stream_frames_stops_on_none():
    from app.services.video_stream import RTSPStreamReader

    reader = RTSPStreamReader("rtsp://localhost:8554/camera")
    reader.read_frame = AsyncMock(return_value=None)

    frames = []
    async for item in reader.stream_frames():
        frames.append(item)

    assert frames == []


def test_stop_releases_capture():
    from app.services.video_stream import RTSPStreamReader

    reader = RTSPStreamReader("rtsp://localhost:8554/camera")
    reader.running = True
    mock_cap = MagicMock()
    reader.cap = mock_cap

    reader.stop()

    assert reader.running is False
    mock_cap.release.assert_called_once()
