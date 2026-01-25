"""
Pytest fixtures for RT-DETR tests
"""
import sys
from pathlib import Path

import pytest
import numpy as np
import cv2

# Add app directory to path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

# Ensure the rt-detr package named "app" wins over other modules
existing_app = sys.modules.get("app")
if existing_app is not None:
    module_file = getattr(existing_app, "__file__", "") or ""
    if str(app_dir) not in module_file:
        del sys.modules["app"]


@pytest.fixture
def sample_image():
    """Create a sample test image (100x100 white image)"""
    return np.ones((100, 100, 3), dtype=np.uint8) * 255


@pytest.fixture
def sample_image_with_objects():
    """Create a sample image simulating detected objects"""
    # Create a dark background
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    # Draw a simple "person" - rectangle at center
    cv2.rectangle(image, (280, 150), (360, 400), (0, 0, 142), -1)

    # Draw a "car" - rectangle at bottom right
    cv2.rectangle(image, (400, 300), (550, 450), (0, 0, 230), -1)

    return image


@pytest.fixture
def mock_detection_result():
    """Mock detection result for testing"""
    return {
        "class_id": 0,
        "class_name": "person",
        "bbox": [280, 150, 360, 400],
        "confidence": 0.85
    }


@pytest.fixture
def mock_detection_results():
    """List of mock detection results"""
    return [
        {
            "class_id": 0,
            "class_name": "person",
            "bbox": [100, 100, 200, 300],
            "confidence": 0.92
        },
        {
            "class_id": 2,
            "class_name": "car",
            "bbox": [300, 200, 450, 350],
            "confidence": 0.78
        },
        {
            "class_id": 7,
            "class_name": "truck",
            "bbox": [500, 180, 620, 320],
            "confidence": 0.65
        }
    ]


@pytest.fixture
def small_test_image():
    """Create a small test image (50x50)"""
    return np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)


@pytest.fixture
def mock_ultralytics_rtdetr(monkeypatch):
    """Mock RTDETR model to avoid loading actual model during tests"""
    class MockBoxes:
        def __init__(self, detections):
            self._detections = detections

        @property
        def cls(self):
            return self._detections['cls']

        @property
        def conf(self):
            return self._detections['conf']

        @property
        def xyxy(self):
            return self._detections['xyxy']

    class MockResult:
        def __init__(self, detections):
            self.boxes = MockBoxes(detections)

    class MockRTDETR:
        def __init__(self, *args, **kwargs):
            self.call_count = 0

        def __call__(self, image, verbose=False):
            self.call_count += 1
            # Return mock detections
            mock_detections = {
                'cls': np.array([0.0, 2.0]),
                'conf': np.array([0.85, 0.72]),
                'xyxy': np.array([
                    [100.0, 100.0, 200.0, 300.0],
                    [300.0, 200.0, 450.0, 350.0]
                ])
            }
            return [MockResult(mock_detections)]

    # Patch the import and class
    import types
    mock_module = types.ModuleType('ultralytics')
    mock_module.RTDETR = MockRTDETR
    monkeypatch.setitem(sys.modules, 'ultralytics', mock_module)

    return MockRTDETR
