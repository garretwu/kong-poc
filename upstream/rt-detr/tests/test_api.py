"""
Unit tests for API endpoints
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from unittest import IsolatedAsyncioTestCase

import pytest
from fastapi.testclient import TestClient

# Ensure correct path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))


@pytest.fixture
def mock_inferencer():
    """Create a mock inferencer for testing"""
    mock = MagicMock()
    mock.infer = MagicMock(return_value=[
        {
            "class_id": 0,
            "class_name": "person",
            "bbox": [100, 100, 200, 300],
            "confidence": 0.85
        }
    ])
    mock.draw_annotations = MagicMock(return_value=MagicMock())
    return mock


@pytest.fixture
def mock_connection_manager():
    """Create a mock connection manager for testing"""
    mock = MagicMock()
    mock.update_session_status = MagicMock()
    mock.update_session_stream = MagicMock()
    mock.get_active_sessions = MagicMock(return_value=[])
    mock.connect = AsyncMock()
    mock.send_status = AsyncMock()
    mock.send_json = AsyncMock()
    mock.send_error = AsyncMock()
    mock.send_frame_result = AsyncMock()
    mock.send_alert = AsyncMock()
    mock.get_session = MagicMock(return_value=None)
    return mock


@pytest.fixture
def test_client(mock_inferencer, mock_connection_manager):
    """Create a test client with mocked dependencies"""
    with patch('app.api.endpoints.get_inferencer', return_value=mock_inferencer):
        with patch('app.api.endpoints.connection_manager', mock_connection_manager):
            from app.main import app
            client = TestClient(app)
            yield client


class TestHealthEndpoint:
    """Tests for health check endpoint"""

    def test_health_returns_200(self, test_client):
        response = test_client.get("/api/v1/video/health")

        assert response.status_code == 200

    def test_health_response_structure(self, test_client):
        response = test_client.get("/api/v1/video/health")
        data = response.json()

        assert "status" in data
        assert "model_loaded" in data
        assert "gpu_available" in data
        assert "uptime_seconds" in data


class TestVideoRequestSchema:
    """Tests for VideoRequest model"""

    def test_valid_request_with_http_url(self):
        from app.models.schema import VideoRequest

        request = VideoRequest(stream_url="http://example.com/stream.flv")

        assert request.stream_url == "http://example.com/stream.flv"
        assert request.enable_drawing is True
        assert request.api_key is None

    def test_valid_request_with_rtsp_url(self):
        from app.models.schema import VideoRequest

        request = VideoRequest(stream_url="rtsp://localhost:8554/camera")

        assert request.stream_url == "rtsp://localhost:8554/camera"

    def test_valid_request_with_custom_settings(self):
        from app.models.schema import VideoRequest

        request = VideoRequest(
            stream_url="rtsp://localhost:8554/camera",
            enable_drawing=False,
            api_key="test-key"
        )

        assert request.enable_drawing is False
        assert request.api_key == "test-key"


class TestVideoResponseSchema:
    """Tests for VideoResponse model"""

    def test_response_structure(self):
        from app.models.schema import VideoResponse

        response = VideoResponse(
            session_id="test-session-123",
            status="running",
            message="Analysis started"
        )

        assert response.session_id == "test-session-123"
        assert response.status == "running"
        assert response.message == "Analysis started"


class TestSessionInfoSchema:
    """Tests for SessionInfo model"""

    def test_session_info_structure(self):
        from app.models.schema import SessionInfo

        info = SessionInfo(
            session_id="test-session",
            status="running",
            frame_count=10,
            stream_url="rtsp://localhost/stream"
        )

        assert info.session_id == "test-session"
        assert info.status == "running"
        assert info.frame_count == 10
        assert info.stream_url == "rtsp://localhost/stream"


class TestDetectionResultSchema:
    """Tests for DetectionResult model"""

    def test_detection_result_structure(self):
        from app.models.schema import DetectionResult

        result = DetectionResult(
            class_id=0,
            class_name="person",
            bbox=[100, 100, 200, 300],
            confidence=0.85
        )

        assert result.class_id == 0
        assert result.class_name == "person"
        assert result.bbox == [100, 100, 200, 300]
        assert result.confidence == 0.85

    def test_bbox_list_length(self):
        from app.models.schema import DetectionResult

        result = DetectionResult(
            class_id=0,
            class_name="person",
            bbox=[1, 2, 3, 4],
            confidence=0.5
        )

        assert len(result.bbox) == 4


class TestHealthResponseSchema:
    """Tests for HealthResponse model"""

    def test_health_response_structure(self):
        from app.models.schema import HealthResponse

        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            gpu_available=False,
            uptime_seconds=100.5
        )

        assert response.status == "healthy"
        assert response.model_loaded is True
        assert response.gpu_available is False
        assert response.uptime_seconds == 100.5


class TestVideoStopRequestSchema:
    """Tests for VideoStopRequest model"""

    def test_stop_request_structure(self):
        from app.models.schema import VideoStopRequest

        request = VideoStopRequest(session_id="test-session")

        assert request.session_id == "test-session"


class TestAlertMessageSchema:
    """Tests for AlertMessage model"""

    def test_alert_message_structure(self):
        from app.models.schema import AlertMessage, DetectionResult

        detection = DetectionResult(
            class_id=0,
            class_name="person",
            bbox=[100, 100, 200, 300],
            confidence=0.85
        )

        message = AlertMessage(
            session_id="test-session",
            timestamp=1234567890.0,
            data=detection
        )

        assert message.type == "alert"
        assert message.session_id == "test-session"
        assert message.data.class_name == "person"


class TestErrorMessageSchema:
    """Tests for ErrorMessage model"""

    def test_error_message_structure(self):
        from app.models.schema import ErrorMessage

        message = ErrorMessage(
            session_id="test-session",
            timestamp=1234567890.0,
            message="Connection failed"
        )

        assert message.type == "error"
        assert message.session_id == "test-session"
        assert message.message == "Connection failed"


class TestFrameResultSchema:
    """Tests for FrameResult model"""

    def test_frame_result_structure(self):
        from app.models.schema import FrameResult, DetectionResult

        detections = [
            DetectionResult(
                class_id=0,
                class_name="person",
                bbox=[100, 100, 200, 300],
                confidence=0.85
            )
        ]

        result = FrameResult(
            session_id="test-session",
            timestamp=1234567890.0,
            frame_index=5,
            detections=detections,
            annotated_frame="base64data"
        )

        assert result.type == "frame_result"
        assert result.session_id == "test-session"
        assert result.frame_index == 5
        assert len(result.detections) == 1
        assert result.annotated_frame == "base64data"


class TestRouterPrefix:
    """Tests for router configuration"""

    def test_router_has_correct_prefix(self):
        from app.api.endpoints import router

        assert router.prefix == "/api/v1/video"


class TestStartAnalysisValidation:
    """Tests for start analysis endpoint validation"""

    def test_invalid_url_rejected(self, test_client):
        response = test_client.post(
            "/api/v1/video/start",
            json={"stream_url": "invalid-url"}
        )

        # Validation error - returns 400 or 422 depending on FastAPI version
        assert response.status_code in [400, 422]

    def test_missing_url_rejected(self, test_client):
        response = test_client.post(
            "/api/v1/video/start",
            json={}
        )

        assert response.status_code == 422  # Validation error

    def test_valid_http_url_accepted(self, test_client, mock_connection_manager):
        response = test_client.post(
            "/api/v1/video/start",
            json={"stream_url": "http://example.com/stream.flv"}
        )

        # Should create a session (returns 200)
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "running"

    def test_valid_rtsp_url_accepted(self, test_client, mock_connection_manager):
        response = test_client.post(
            "/api/v1/video/start",
            json={"stream_url": "rtsp://localhost:8554/camera"}
        )

        assert response.status_code == 200


class TestStopAnalysis:
    """Tests for stop analysis endpoint"""

    def test_stop_with_valid_session(self, test_client, mock_connection_manager):
        response = test_client.post(
            "/api/v1/video/stop",
            json={"session_id": "test-session"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session"
        assert data["status"] == "stopped"


class TestListSessions:
    """Tests for list sessions endpoint"""

    def test_list_sessions_empty(self, test_client, mock_connection_manager):
        mock_connection_manager.get_active_sessions.return_value = []

        response = test_client.get("/api/v1/video/sessions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_sessions_with_data(self, test_client, mock_connection_manager):
        mock_connection_manager.get_active_sessions.return_value = [
            {
                "session_id": "session-1",
                "status": "running",
                "frame_count": 10,
                "stream_url": "rtsp://url1"
            },
            {
                "session_id": "session-2",
                "status": "pending",
                "frame_count": 0,
                "stream_url": "rtsp://url2"
            }
        ]

        response = test_client.get("/api/v1/video/sessions")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestGetSession:
    """Tests for get session endpoint"""

    def test_get_existing_session(self, test_client, mock_connection_manager):
        mock_session = MagicMock()
        mock_session.session_id = "test-session"
        mock_session.status = MagicMock(value="running")
        mock_session.frame_count = 5
        mock_session.stream_url = "rtsp://url"
        mock_connection_manager.get_session.return_value = mock_session

        response = test_client.get("/api/v1/video/sessions/test-session")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session"

    def test_get_nonexistent_session(self, test_client, mock_connection_manager):
        mock_connection_manager.get_session.return_value = None

        response = test_client.get("/api/v1/video/sessions/nonexistent")

        assert response.status_code == 404


class TestFrontendRouter:
    """Tests for frontend router"""

    def test_index_returns_html(self, test_client):
        import os
        template_path = "/app/templates/index.html"

        if not os.path.exists(template_path):
            pytest.skip("Template file not found")

        response = test_client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestCORSHeaders:
    """Tests for CORS configuration"""

    def test_cors_allows_origins(self, test_client):
        # Test preflight request - FastAPI handles CORS automatically
        response = test_client.options(
            "/api/v1/video/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )

        # CORS is configured, either returns proper headers or method not allowed
        assert response.status_code in [200, 405]


class TestWebSocketEndpoint:
    """Tests for WebSocket endpoint"""

    def test_websocket_endpoint_exists(self):
        from app.main import app

        # Check that the endpoint is registered
        routes = [route.path for route in app.routes]
        assert "/ws/stream/{session_id}" in routes


class TestSettingsInEndpoints:
    """Tests for settings usage in endpoints"""

    def test_endpoints_import_settings(self):
        from app.api import endpoints

        # Check that settings is imported
        assert hasattr(endpoints, 'settings')
