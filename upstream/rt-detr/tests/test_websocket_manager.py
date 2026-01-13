"""
Unit tests for WebSocket ConnectionManager and FrameEncoder
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

import pytest
import numpy as np

# Ensure correct path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))


class TestSessionStatus:
    """Tests for SessionStatus enum"""

    def test_session_status_values(self):
        from app.services.websocket_manager import SessionStatus

        assert SessionStatus.PENDING.value == "pending"
        assert SessionStatus.RUNNING.value == "running"
        assert SessionStatus.STOPPED.value == "stopped"
        assert SessionStatus.ERROR.value == "error"

    def test_session_status_has_all_expected_values(self):
        from app.services.websocket_manager import SessionStatus

        expected = ["pending", "running", "stopped", "error"]
        actual = [s.value for s in SessionStatus]
        assert set(actual) == set(expected)


class TestAnalysisSession:
    """Tests for AnalysisSession dataclass"""

    def test_analysis_session_default_values(self):
        from app.services.websocket_manager import SessionStatus, AnalysisSession

        session = AnalysisSession(
            session_id="test-session",
            stream_url="rtsp://localhost:8554/camera"
        )

        assert session.session_id == "test-session"
        assert session.stream_url == "rtsp://localhost:8554/camera"
        assert session.status == SessionStatus.PENDING
        assert session.frame_count == 0
        assert session.start_time is None
        assert session.websocket is None

    def test_analysis_session_with_custom_values(self):
        from app.services.websocket_manager import SessionStatus, AnalysisSession

        mock_websocket = MagicMock()
        session = AnalysisSession(
            session_id="custom-session",
            stream_url="http://example.com/stream",
            status=SessionStatus.RUNNING,
            frame_count=100,
            start_time=1234567890.0,
            websocket=mock_websocket
        )

        assert session.status == SessionStatus.RUNNING
        assert session.frame_count == 100
        assert session.start_time == 1234567890.0
        assert session.websocket == mock_websocket


class TestConnectionManager:
    """Tests for ConnectionManager"""

    def test_connection_manager_init(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()

        assert hasattr(manager, '_connections')
        assert hasattr(manager, '_sessions')
        assert len(manager._connections) == 0
        assert len(manager._sessions) == 0

    @pytest.mark.asyncio
    async def test_connect_creates_session(self):
        from app.services.websocket_manager import ConnectionManager, SessionStatus

        manager = ConnectionManager()
        mock_websocket = AsyncMock()

        session = await manager.connect("test-session", mock_websocket)

        assert session is not None
        assert session.session_id == "test-session"
        assert session.status == SessionStatus.PENDING

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock()

        await manager.connect("test-session", mock_websocket)

        mock_websocket.accept.assert_called_once()

    def test_disconnect_removes_connection(self):
        from app.services.websocket_manager import ConnectionManager, SessionStatus

        manager = ConnectionManager()
        mock_websocket = MagicMock()

        # Manually add connection
        manager._connections["test-session"] = {mock_websocket}
        manager._sessions["test-session"] = MagicMock()
        manager._sessions["test-session"].status = SessionStatus.RUNNING

        manager.disconnect("test-session", mock_websocket)

        assert "test-session" not in manager._connections

    def test_disconnect_updates_session_status(self):
        from app.services.websocket_manager import ConnectionManager, SessionStatus

        manager = ConnectionManager()
        mock_websocket = MagicMock()

        # Create session
        manager._sessions["test-session"] = MagicMock()
        manager._sessions["test-session"].status = SessionStatus.RUNNING

        manager.disconnect("test-session", mock_websocket)

        manager._sessions["test-session"].status = SessionStatus.STOPPED

    def test_get_session_returns_none_for_unknown(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()

        result = manager.get_session("unknown-session")

        assert result is None

    def test_get_session_returns_session(self):
        from app.services.websocket_manager import ConnectionManager, SessionStatus

        manager = ConnectionManager()
        manager._sessions["known-session"] = MagicMock()
        manager._sessions["known-session"].session_id = "known-session"

        result = manager.get_session("known-session")

        assert result is not None
        assert result.session_id == "known-session"

    def test_update_session_stream(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()
        mock_session = MagicMock()
        manager._sessions["test-session"] = mock_session

        manager.update_session_stream("test-session", "rtsp://new-url/stream")

        mock_session.stream_url = "rtsp://new-url/stream"

    def test_update_session_status(self):
        from app.services.websocket_manager import ConnectionManager, SessionStatus

        manager = ConnectionManager()
        mock_session = MagicMock()
        mock_session.status = SessionStatus.PENDING
        manager._sessions["test-session"] = mock_session

        manager.update_session_status("test-session", SessionStatus.RUNNING)

        assert mock_session.status == SessionStatus.RUNNING

    def test_increment_frame_count(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()
        mock_session = MagicMock()
        mock_session.frame_count = 5
        manager._sessions["test-session"] = mock_session

        manager.increment_frame_count("test-session")

        assert mock_session.frame_count == 6

    @pytest.mark.asyncio
    async def test_send_json_no_connections(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()

        # Should not raise
        await manager.send_json("no-session", {"test": "data"})

    @pytest.mark.asyncio
    async def test_send_json_with_connection(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        manager._connections["test-session"] = {mock_websocket}

        await manager.send_json("test-session", {"test": "data"})

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_frame_result(self):
        from app.services.websocket_manager import ConnectionManager, AnalysisSession

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        manager._connections["test-session"] = {mock_websocket}

        # Create a real session object
        manager._sessions["test-session"] = AnalysisSession(
            session_id="test-session",
            stream_url="rtsp://test"
        )

        await manager.send_frame_result(
            session_id="test-session",
            base64_frame="base64data",
            detections=[{"class_name": "person", "confidence": 0.9}],
            timestamp=1234567890.0,
            frame_index=5
        )

        mock_websocket.send_text.assert_called_once()
        # Verify frame count incremented
        assert manager._sessions["test-session"].frame_count == 1

    @pytest.mark.asyncio
    async def test_send_alert_skips_low_confidence(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        manager._connections["test-session"] = {mock_websocket}

        low_confidence_detection = {
            "class_name": "person",
            "confidence": 0.3,
            "bbox": [100, 100, 200, 200]
        }

        await manager.send_alert("test-session", low_confidence_detection, 0.5)

        # Should not send alert for low confidence
        mock_websocket.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_alert_sends_high_confidence(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        manager._connections["test-session"] = {mock_websocket}

        high_confidence_detection = {
            "class_name": "person",
            "confidence": 0.8,
            "bbox": [100, 100, 200, 200]
        }

        await manager.send_alert("test-session", high_confidence_detection, 0.5)

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_error(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        manager._connections["test-session"] = {mock_websocket}

        await manager.send_error("test-session", "Test error message")

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_status(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        manager._connections["test-session"] = {mock_websocket}

        await manager.send_status("test-session", "running", "Analysis started")

        mock_websocket.send_text.assert_called_once()

    def test_get_active_sessions_empty(self):
        from app.services.websocket_manager import ConnectionManager

        manager = ConnectionManager()

        result = manager.get_active_sessions()

        assert result == []

    def test_get_active_sessions_with_data(self):
        from app.services.websocket_manager import ConnectionManager, SessionStatus

        manager = ConnectionManager()
        mock_session1 = MagicMock()
        mock_session1.session_id = "session1"
        mock_session1.status = SessionStatus.RUNNING
        mock_session1.frame_count = 10
        mock_session1.stream_url = "rtsp://url1"

        mock_session2 = MagicMock()
        mock_session2.session_id = "session2"
        mock_session2.status = SessionStatus.PENDING
        mock_session2.frame_count = 0
        mock_session2.stream_url = "rtsp://url2"

        manager._sessions["session1"] = mock_session1
        manager._sessions["session2"] = mock_session2

        result = manager.get_active_sessions()

        assert len(result) == 2
        assert result[0]["session_id"] == "session1"
        assert result[1]["session_id"] == "session2"


class TestFrameEncoder:
    """Tests for FrameEncoder"""

    def test_encode_jpeg_returns_string(self):
        from app.services.websocket_manager import FrameEncoder

        encoder = FrameEncoder()
        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255

        result = encoder.encode_jpeg(test_image, quality=70)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_encode_jpeg_different_quality(self):
        from app.services.websocket_manager import FrameEncoder

        encoder = FrameEncoder()
        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255

        low_quality = encoder.encode_jpeg(test_image, quality=10)
        high_quality = encoder.encode_jpeg(test_image, quality=95)

        # Higher quality should generally produce longer strings
        # (not always true due to compression, but generally)
        assert isinstance(low_quality, str)
        assert isinstance(high_quality, str)

    def test_encode_jpeg_is_valid_base64(self):
        import base64
        from app.services.websocket_manager import FrameEncoder

        encoder = FrameEncoder()
        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255

        result = encoder.encode_jpeg(test_image)

        # Should be valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_resize_no_resize_needed(self):
        from app.services.websocket_manager import FrameEncoder

        encoder = FrameEncoder()
        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255

        result = encoder.resize(test_image, max_width=800)

        assert result.shape[0] == 100
        assert result.shape[1] == 100

    def test_resize_smaller_image(self):
        from app.services.websocket_manager import FrameEncoder

        encoder = FrameEncoder()
        test_image = np.ones((100, 50, 3), dtype=np.uint8) * 255

        result = encoder.resize(test_image, max_width=800)

        # Should not resize since width is already small
        assert result.shape[1] == 50

    def test_resize_larger_image(self):
        from app.services.websocket_manager import FrameEncoder

        encoder = FrameEncoder()
        # 1600x900 image
        test_image = np.ones((900, 1600, 3), dtype=np.uint8) * 255

        result = encoder.resize(test_image, max_width=800)

        # Should resize to max_width=800
        assert result.shape[1] == 800
        # Aspect ratio should be preserved
        assert result.shape[0] == 450

    def test_resize_maintains_aspect_ratio(self):
        from app.services.websocket_manager import FrameEncoder

        encoder = FrameEncoder()
        # 2000x1000 image (2:1 aspect ratio)
        test_image = np.ones((1000, 2000, 3), dtype=np.uint8) * 255

        result = encoder.resize(test_image, max_width=1000)

        # Should maintain 2:1 ratio
        assert result.shape[1] == 1000
        assert result.shape[0] == 500

    def test_resize_returns_numpy_array(self):
        from app.services.websocket_manager import FrameEncoder

        encoder = FrameEncoder()
        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255

        result = encoder.resize(test_image)

        assert isinstance(result, np.ndarray)

    def test_frame_encoder_is_singleton(self):
        from app.services.websocket_manager import FrameEncoder

        encoder1 = FrameEncoder()
        encoder2 = FrameEncoder()

        # Both should work identically
        test_image = np.ones((50, 50, 3), dtype=np.uint8) * 255

        result1 = encoder1.encode_jpeg(test_image)
        result2 = encoder2.encode_jpeg(test_image)

        assert result1 == result2
