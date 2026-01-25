"""
Unit tests for configuration module
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure correct path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))


class TestSettings:
    """Tests for Settings configuration"""

    def test_default_values(self):
        from app.config import Settings

        settings = Settings()

        # Model defaults
        assert settings.model_path == "/models/rt-detr.pt"
        assert settings.device == "cuda"
        assert settings.confidence_threshold == 0.5

        # Server defaults
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.debug is False

        # Video defaults
        assert settings.stream_timeout == 30
        assert settings.frame_quality == 70
        assert settings.max_frame_width == 800

        # Alert defaults
        assert settings.alert_enabled is True
        assert settings.alert_confidence_threshold == 0.7

        # Kong defaults
        assert settings.kong_api_url is None

    def test_custom_values(self):
        from app.config import Settings

        settings = Settings(
            model_path="/custom/path/model.pt",
            device="cpu",
            confidence_threshold=0.7,
            host="127.0.0.1",
            port=9000,
            debug=True
        )

        assert settings.model_path == "/custom/path/model.pt"
        assert settings.device == "cpu"
        assert settings.confidence_threshold == 0.7
        assert settings.host == "127.0.0.1"
        assert settings.port == 9000
        assert settings.debug is True

    def test_env_prefix(self):
        from app.config import Settings

        settings = Settings()

        assert settings.Config.env_prefix == "RT_DETR_"

    def test_model_path_validation(self):
        from app.config import Settings

        # Test with typical model path
        settings = Settings(model_path="/models/rt-detr.pt")
        assert settings.model_path == "/models/rt-detr.pt"

        # Test with relative path
        settings = Settings(model_path="./models/my-model.pt")
        assert settings.model_path == "./models/my-model.pt"

    def test_device_validation(self):
        from app.config import Settings

        # Test with cuda
        settings = Settings(device="cuda")
        assert settings.device == "cuda"

        # Test with cpu
        settings = Settings(device="cpu")
        assert settings.device == "cpu"

    def test_confidence_threshold_range(self):
        from app.config import Settings

        # Valid thresholds
        settings_low = Settings(confidence_threshold=0.1)
        assert settings_low.confidence_threshold == 0.1

        settings_mid = Settings(confidence_threshold=0.5)
        assert settings_mid.confidence_threshold == 0.5

        settings_high = Settings(confidence_threshold=0.99)
        assert settings_high.confidence_threshold == 0.99

    def test_frame_quality_range(self):
        from app.config import Settings

        # Valid quality values
        settings_low = Settings(frame_quality=10)
        assert settings_low.frame_quality == 10

        settings_mid = Settings(frame_quality=70)
        assert settings_mid.frame_quality == 70

        settings_high = Settings(frame_quality=100)
        assert settings_high.frame_quality == 100

    def test_max_frame_width(self):
        from app.config import Settings

        settings = Settings(max_frame_width=1280)
        assert settings.max_frame_width == 1280

        settings_small = Settings(max_frame_width=400)
        assert settings_small.max_frame_width == 400

    def test_alert_settings(self):
        from app.config import Settings

        # Alert enabled
        settings = Settings(alert_enabled=True, alert_confidence_threshold=0.8)
        assert settings.alert_enabled is True
        assert settings.alert_confidence_threshold == 0.8

        # Alert disabled
        settings = Settings(alert_enabled=False)
        assert settings.alert_enabled is False

    def test_kong_api_url_optional(self):
        from app.config import Settings

        # Without Kong URL
        settings = Settings()
        assert settings.kong_api_url is None

        # With Kong URL
        settings = Settings(kong_api_url="http://kong:8001")
        assert settings.kong_api_url == "http://kong:8001"

    def test_stream_timeout(self):
        from app.config import Settings

        settings = Settings(stream_timeout=60)
        assert settings.stream_timeout == 60

    def test_settings_equality(self):
        from app.config import Settings

        settings1 = Settings(port=8080)
        settings2 = Settings(port=8080)
        settings3 = Settings(port=9000)

        assert settings1 == settings2
        assert settings1 != settings3

    def test_settings_repr(self):
        from app.config import Settings

        settings = Settings(port=8080)
        repr_str = repr(settings)

        assert "Settings" in repr_str
        assert "port" in repr_str
        assert "8080" in repr_str

    def test_settings_json_schema(self):
        from app.config import Settings

        settings = Settings()
        schema = settings.model_json_schema()

        assert "title" in schema
        assert "model_path" in schema["properties"]
        assert "device" in schema["properties"]
        assert "confidence_threshold" in schema["properties"]


class TestGetSettings:
    """Tests for get_settings function"""

    def test_get_settings_returns_settings(self):
        from app.config import get_settings, Settings

        settings = get_settings()

        assert isinstance(settings, Settings)
        assert settings.model_path == "/models/rt-detr.pt"

    def test_get_settings_returns_new_instance(self):
        from app.config import get_settings

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be equal in value but different objects
        assert settings1 == settings2
        assert settings1 is not settings2


class TestSettingsAsSingleton:
    """Tests for settings module-level singleton"""

    def test_settings_module_is_singleton(self):
        from app.config import settings

        # Import twice to ensure same instance
        from app import config as config_module

        assert settings is config_module.settings

    def test_settings_default_values_correct(self):
        from app.config import settings

        # Verify the default settings
        assert settings.port == 8080
        assert settings.host == "0.0.0.0"
        assert settings.device == "cuda"
        assert settings.confidence_threshold == 0.5

    def test_settings_can_be_modified(self):
        from app.config import settings

        original_port = settings.port

        # Modify
        settings.port = 9999
        assert settings.port == 9999

        # Restore
        settings.port = original_port
