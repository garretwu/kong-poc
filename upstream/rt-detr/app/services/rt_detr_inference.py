"""
RT-DETRv2 推理模块
支持 COCO 80类目标检测
"""

from typing import List, Dict, Any
import cv2
import numpy as np


class RTDETRv2Inferencer:
    """RT-DETRv2 推理器 (COCO 80类)"""

    COCO_CLASSES = [
        'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train',
        'truck', 'boat', 'traffic light', 'fire hydrant', 'stop sign',
        'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep',
        'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella',
        'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
        'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard',
        'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon',
        'bowl', 'banana', 'apple', 'sandwich', 'orange', 'broccoli', 'carrot',
        'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch', 'potted plant',
        'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
        'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
        'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear',
        'hair drier', 'toothbrush'
     ]

    #类别颜色映射 (BGR 格式)
    CLASS_COLORS = [
        (220, 20, 60), (119, 11, 32), (0, 0, 142), (0, 0, 230), (106, 0, 228),
        (0, 60, 100), (0, 80, 100), (0, 0, 192), (250, 170, 30), (100, 170, 30),
        (220, 220, 0), (175, 116, 175), (250, 0, 30), (165, 42, 42), (255, 77, 255),
        (0, 226, 252), (182, 182, 255), (0, 82, 0), (120, 166, 157), (110, 76, 0),
        (174, 57, 255), (199, 100, 0), (72, 0, 118), (87, 69, 218), (66, 102, 0),
        (197, 184, 0), (75, 0, 75), (151, 0, 0), (71, 0, 44), (0, 163, 0),
        (232, 0, 31), (0, 182, 199), (0, 192, 219), (195, 195, 135), (135, 206, 235),
        (44, 156, 168), (0, 132, 0), (186, 156, 0), (148, 156, 0), (50, 132, 191),
        (166, 147, 0), (255, 189, 53), (255, 174, 27), (255, 153, 0), (191, 255, 0),
        (0, 153, 255), (255, 127, 0), (0, 102, 255), (255, 51, 0), (255, 0, 102),
        (153, 255, 0), (102, 0, 255), (153, 0, 255), (0, 255, 204), (0, 255, 51),
        (0, 255, 153), (0, 255, 102), (51, 255, 0), (0, 255, 0), (0, 204, 255),
        (0, 102, 204), (0, 204, 0), (0, 255, 153), (0, 153, 204), (0, 51, 255),
        (0, 0, 153), (0, 0, 255), (0, 51, 0), (0, 102, 0), (0, 51, 153),
        (51, 153, 0), (0, 153, 0), (0, 102, 153), (51, 0, 153), (102, 0, 153)
    ]

    def __init__(self, model_path: str, device: str = "cuda", confidence_threshold: float = 0.5):
        """初始化 RT-DETRv2 推理器

        Args:
            model_path: 模型文件路径 (.pt)
            device: 运行设备 ("cuda" 或 "cpu")
            confidence_threshold: 检测置信度阈值
        """
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.model = self._load_model(model_path)

    def _load_model(self, model_path: str):
        """加载 RT-DETRv2 模型"""
        try:
            from ultralytics import RTDETR
            model = RTDETR(model_path)
            return model
        except ImportError:
            raise ImportError("Please install ultralytics: pip install ultralytics")

    def infer(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """推理单帧图像

        Args:
            image: OpenCV BGR 格式图像

        Returns:
            检测结果列表
        """
        # 转换为 RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 推理
        results = self.model(rgb_image, verbose=False)

        # 解析结果
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for i in range(len(boxes)):
                    cls = int(boxes.cls[i])
                    conf = float(boxes.conf[i])

                    if conf < self.confidence_threshold:
                        continue

                    xyxy = boxes.xyxy[i].cpu().numpy()
                    detections.append({
                        "class_id": cls,
                        "class_name": self.COCO_CLASSES[cls] if cls < len(self.COCO_CLASSES) else f"class_{cls}",
                        "bbox": xyxy.tolist(),  # [x1, y1, x2, y2]
                        "confidence": conf
                    })

        return detections

    def draw_annotations(
        self,
        image: np.ndarray,
        detections: List[Dict[str, Any]],
        show_confidence: bool = True
    ) -> np.ndarray:
        """绘制检测框 (COCO 80类可视化)

        Args:
            image: 原始图像 (BGR)
            detections: 检测结果列表
            show_confidence: 是否显示置信度

        Returns:
            绘制后的图像
        """
        for det in detections:
            x1, y1, x2, y2 = map(int, det["bbox"])
            cls_id = det["class_id"]
            conf = det["confidence"]
            class_name = det["class_name"]

            # 获取类别颜色
            color = self.CLASS_COLORS[cls_id % len(self.CLASS_COLORS)]

            # 绘制边界框
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

            # 构建标签
            if show_confidence:
                label = f"{class_name}: {conf:.2f}"
            else:
                label = class_name

            # 获取文字尺寸
            (text_w, text_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )

            # 绘制标签背景
            cv2.rectangle(
                image,
                (x1, y1 - text_h - 10),
                (x1 + text_w, y1),
                color,
                -1
            )

            # 绘制标签文字
            cv2.putText(
                image,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

        return image

    def simulate_alert(self, detection: dict) -> str:
        """生成告警消息（简单模拟：控制台打印格式）

        Args:
            detection: 单个检测结果

        Returns:
            告警消息字符串
        """
        return f"[ALERT] 检测到 {detection['class_name']} " \
               f"置信度: {detection['confidence']:.2%} " \
               f"位置: {detection['bbox']}"
