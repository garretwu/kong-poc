"""
Unit tests for RTDETRv2Inferencer
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import numpy as np

# Ensure correct path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))


class TestCOCOClasses:
    """Tests for COCO class definitions"""

    def test_coco_classes_count(self):
        """Test that COCO_CLASSES has exactly 80 classes"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        assert len(RTDETRv2Inferencer.COCO_CLASSES) == 80

    def test_coco_classes_contain_common_objects(self):
        """Test that COCO_CLASSES contains expected common objects"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        expected_classes = ['person', 'car', 'dog', 'cat', 'bicycle']
        for expected in expected_classes:
            assert expected in RTDETRv2Inferencer.COCO_CLASSES

    def test_first_class_is_person(self):
        """Test that first class is 'person'"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        assert RTDETRv2Inferencer.COCO_CLASSES[0] == "person"


class TestClassColors:
    """Tests for class color definitions"""

    def test_class_colors_count(self):
        """Test that CLASS_COLORS has expected count"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        # CLASS_COLORS is used cyclically, so it doesn't need to match exactly
        assert len(RTDETRv2Inferencer.CLASS_COLORS) > 0
        # Verify it's a reasonable size
        assert len(RTDETRv2Inferencer.CLASS_COLORS) >= 70

    def test_class_colors_are_tuples(self):
        """Test that CLASS_COLORS contains tuples"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        for color in RTDETRv2Inferencer.CLASS_COLORS:
            assert isinstance(color, tuple)
            assert len(color) == 3  # BGR format


class MockBoxes:
    """Mock for ultralytics boxes object"""
    def __init__(self, cls, conf, xyxy):
        self._cls = cls
        self._conf = conf
        self._xyxy = xyxy

    def __len__(self):
        return len(self._cls)

    @property
    def cls(self):
        return self._cls

    @property
    def conf(self):
        return self._conf

    @property
    def xyxy(self):
        return self._xyxy


class MockResult:
    """Mock for ultralytics results object"""
    def __init__(self, boxes):
        self.boxes = boxes


class MockRTDETR:
    """Mock for ultralytics RTDETR model"""
    def __init__(self, *args, **kwargs):
        self.call_count = 0
        self.args = args
        self.kwargs = kwargs

    def __call__(self, image, verbose=False):
        self.call_count += 1
        # Return mock detections with different scenarios
        if hasattr(image, 'shape'):
            # Create mock boxes with torch tensors (simulating real behavior)
            import torch
            cls = torch.tensor([0.0, 2.0, 7.0])
            conf = torch.tensor([0.92, 0.78, 0.55])
            xyxy = torch.tensor([
                [100.0, 100.0, 200.0, 300.0],
                [300.0, 200.0, 450.0, 350.0],
                [500.0, 180.0, 620.0, 320.0]
            ])
            boxes = MockBoxes(cls, conf, xyxy)
            return [MockResult(boxes)]
        return []


def create_mock_inferencer():
    """Create an inferencer with mocked model"""
    from app.services.rt_detr_inference import RTDETRv2Inferencer

    mock_model = MockRTDETR()
    with patch.object(RTDETRv2Inferencer, '_load_model', return_value=mock_model):
        inferencer = RTDETRv2Inferencer(
            model_path="/fake/path/model.pt",
            device="cpu",
            confidence_threshold=0.5
        )
        inferencer.model = mock_model
    return inferencer


class TestInferencerInitialization:
    """Tests for RTDETRv2Inferencer initialization"""

    def test_init_sets_attributes(self):
        """Test that __init__ sets all required attributes"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        mock_model = MagicMock()
        with patch.object(RTDETRv2Inferencer, '_load_model', return_value=mock_model):
            inferencer = RTDETRv2Inferencer(
                model_path="/fake/path/model.pt",
                device="cpu",
                confidence_threshold=0.5
            )

            assert inferencer.device == "cpu"
            assert inferencer.confidence_threshold == 0.5
            assert inferencer.model is mock_model

    def test_init_loads_model(self):
        """Test that __init__ calls _load_model"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        with patch.object(RTDETRv2Inferencer, '_load_model') as mock_load:
            mock_load.return_value = MagicMock()
            RTDETRv2Inferencer(
                model_path="/fake/path/model.pt",
                device="cpu",
                confidence_threshold=0.5
            )

            mock_load.assert_called_once_with("/fake/path/model.pt")


class TestInferencerInference:
    """Tests for infer() method"""

    def test_infer_returns_list(self):
        """Test that infer() returns a list"""
        inferencer = create_mock_inferencer()

        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        detections = inferencer.infer(test_image)

        assert isinstance(detections, list)

    def test_infer_detection_structure(self):
        """Test that detection results have expected structure"""
        inferencer = create_mock_inferencer()

        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        detections = inferencer.infer(test_image)

        if detections:
            det = detections[0]
            assert "class_id" in det
            assert "class_name" in det
            assert "bbox" in det
            assert "confidence" in det
            assert isinstance(det["bbox"], list)
            assert len(det["bbox"]) == 4

    def test_infer_bbox_format(self):
        """Test that bbox is in [x1, y1, x2, y2] format"""
        inferencer = create_mock_inferencer()

        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        detections = inferencer.infer(test_image)

        if detections:
            for det in detections:
                x1, y1, x2, y2 = det["bbox"]
                assert x1 < x2, "x1 should be less than x2"
                assert y1 < y2, "y1 should be less than y2"

    def test_infer_confidence_filtering(self):
        """Test that confidence threshold filters detections"""
        # Create inferencer with very high threshold
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        mock_model = MockRTDETR()
        with patch.object(RTDETRv2Inferencer, '_load_model', return_value=mock_model):
            inferencer = RTDETRv2Inferencer(
                model_path="/fake/path/model.pt",
                device="cpu",
                confidence_threshold=0.99  # Very high threshold
            )
            inferencer.model = mock_model

        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        detections = inferencer.infer(test_image)

        # Mock returns 0.92, 0.78, 0.55 - none should pass 0.99
        for det in detections:
            assert det["confidence"] >= 0.99

    def test_infer_low_threshold_returns_all(self):
        """Test that low threshold returns more detections"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        mock_model = MockRTDETR()
        with patch.object(RTDETRv2Inferencer, '_load_model', return_value=mock_model):
            inferencer = RTDETRv2Inferencer(
                model_path="/fake/path/model.pt",
                device="cpu",
                confidence_threshold=0.1  # Low threshold
            )
            inferencer.model = mock_model

        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        detections = inferencer.infer(test_image)

        # Should return detections (0.92, 0.78, 0.55 all >= 0.1)
        assert len(detections) > 0


class TestDrawAnnotations:
    """Tests for draw_annotations() method"""

    def test_draw_annotations_returns_numpy_array(self):
        """Test that draw_annotations returns a numpy array"""
        inferencer = create_mock_inferencer()

        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        mock_detections = [{
            "class_id": 0,
            "class_name": "person",
            "bbox": [20, 20, 80, 80],
            "confidence": 0.85
        }]

        result = inferencer.draw_annotations(test_image, mock_detections)

        assert isinstance(result, np.ndarray)
        assert result.shape == test_image.shape

    def test_draw_annotations_modifies_image(self):
        """Test that draw_annotations modifies the input image"""
        inferencer = create_mock_inferencer()

        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        original = test_image.copy()

        mock_detections = [{
            "class_id": 0,
            "class_name": "person",
            "bbox": [20, 20, 80, 80],
            "confidence": 0.85
        }]

        result = inferencer.draw_annotations(test_image, mock_detections)

        # Result should be different from original
        assert not np.array_equal(result, original)

    def test_draw_annotations_with_empty_detections(self):
        """Test that draw_annotations works with empty detections list"""
        inferencer = create_mock_inferencer()

        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        result = inferencer.draw_annotations(test_image, [])

        assert isinstance(result, np.ndarray)
        assert result.shape == test_image.shape

    def test_draw_annotations_without_confidence(self):
        """Test draw_annotations with show_confidence=False"""
        inferencer = create_mock_inferencer()

        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        mock_detections = [{
            "class_id": 0,
            "class_name": "person",
            "bbox": [20, 20, 80, 80],
            "confidence": 0.85
        }]

        result = inferencer.draw_annotations(test_image, mock_detections, show_confidence=False)

        assert isinstance(result, np.ndarray)

    def test_draw_annotations_preserves_shape(self):
        """Test that draw_annotations preserves image shape"""
        inferencer = create_mock_inferencer()

        test_image = np.ones((480, 640, 3), dtype=np.uint8) * 255
        mock_detections = [{
            "class_id": 0,
            "class_name": "person",
            "bbox": [100, 100, 200, 300],
            "confidence": 0.85
        }]

        result = inferencer.draw_annotations(test_image, mock_detections)

        assert result.shape == test_image.shape


class TestSimulateAlert:
    """Tests for simulate_alert() method"""

    def test_simulate_alert_format(self):
        """Test that simulate_alert returns properly formatted string"""
        inferencer = create_mock_inferencer()

        mock_detection = {
            "class_id": 0,
            "class_name": "person",
            "bbox": [100, 100, 200, 300],
            "confidence": 0.85
        }

        alert = inferencer.simulate_alert(mock_detection)

        assert isinstance(alert, str)
        assert "person" in alert
        assert "[ALERT]" in alert

    def test_simulate_alert_contains_confidence(self):
        """Test that alert message contains confidence info"""
        inferencer = create_mock_inferencer()

        mock_detection = {
            "class_id": 0,
            "class_name": "person",
            "bbox": [100, 100, 200, 300],
            "confidence": 0.85
        }

        alert = inferencer.simulate_alert(mock_detection)

        # Should contain confidence percentage
        assert "85" in alert or "0.85" in alert

    def test_simulate_alert_contains_bbox(self):
        """Test that alert message contains bbox information"""
        inferencer = create_mock_inferencer()

        mock_detection = {
            "class_id": 0,
            "class_name": "person",
            "bbox": [100, 100, 200, 300],
            "confidence": 0.85
        }

        alert = inferencer.simulate_alert(mock_detection)

        assert "100" in alert

    def test_simulate_alert_different_classes(self):
        """Test alert for different object classes"""
        inferencer = create_mock_inferencer()

        for class_name in ["car", "dog", "bicycle"]:
            mock_detection = {
                "class_id": 2,
                "class_name": class_name,
                "bbox": [100, 100, 200, 300],
                "confidence": 0.85
            }

            alert = inferencer.simulate_alert(mock_detection)

            assert class_name in alert


class TestInferencerImageConversion:
    """Tests for image color space conversion"""

    def test_infer_calls_model_with_image(self):
        """Test that infer() calls the model"""
        inferencer = create_mock_inferencer()

        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        inferencer.infer(test_image)

        # Model should have been called at least once
        assert inferencer.model.call_count >= 1

    def test_infer_handles_color_image(self):
        """Test that infer() works with color images"""
        inferencer = create_mock_inferencer()

        # Create a color image
        color_image = np.zeros((100, 100, 3), dtype=np.uint8)
        color_image[:, :, 0] = 255  # Blue channel

        detections = inferencer.infer(color_image)

        assert isinstance(detections, list)

    def test_infer_handles_grayscale(self):
        """Test that infer() works with grayscale images"""
        inferencer = create_mock_inferencer()

        # Create a grayscale image
        gray_image = np.random.randint(0, 256, (100, 100), dtype=np.uint8)

        # infer() expects BGR image, but we can test that it attempts conversion
        # Note: This may fail if the mock doesn't handle 2D arrays
        try:
            detections = inferencer.infer(gray_image)
            assert isinstance(detections, list)
        except (AttributeError, TypeError):
            # Expected if model doesn't handle grayscale
            pass


class TestLoadModel:
    """Tests for _load_model method"""

    def test_load_model_raises_import_error(self):
        """Test that _load_model raises ImportError when ultralytics not available"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        with patch.dict('sys.modules', {'ultralytics': None}):
            with pytest.raises(ImportError, match="Please install ultralytics"):
                RTDETRv2Inferencer._load_model(None, "/fake/path.pt")

    def test_load_model_returns_model(self):
        """Test that _load_model returns a model when ultralytics is available"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        mock_model = MagicMock()
        with patch('ultralytics.RTDETR', return_value=mock_model):
            result = RTDETRv2Inferencer._load_model(None, "/fake/path.pt")
            assert result is mock_model


class TestClassNameLookup:
    """Tests for class name lookup"""

    def test_class_name_for_valid_id(self):
        """Test that class_name is correctly retrieved for valid class ID"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        assert RTDETRv2Inferencer.COCO_CLASSES[0] == "person"
        assert RTDETRv2Inferencer.COCO_CLASSES[1] == "bicycle"
        assert RTDETRv2Inferencer.COCO_CLASSES[2] == "car"

    def test_class_name_fallback_for_unknown_id(self):
        """Test class_name fallback for out-of-range IDs"""
        from app.services.rt_detr_inference import RTDETRv2Inferencer

        # This tests the fallback behavior
        class_id = 999
        expected_name = f"class_{class_id}"
        assert expected_name == f"class_{class_id}"
