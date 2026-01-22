# RTSP 视频流分析系统技术规范

## 1. 概述

### 1.1 目标
构建一个实时视频流分析系统，支持 RTSP 摄像头接入、API 鉴权、负载均衡，并将视频流实时推送至浏览器展示。

### 1.2 技术栈
| 组件 | 技术选型 | 版本要求 |
|------|----------|----------|
| 协议转换 | MediaMTX | >= 1.9.0 |
| 网关 | Kong Gateway | >= 3.0 |
| 后端框架 | FastAPI | >= 0.100 |
| AI 模型 | RT-DETRv2 | 官方最新版 |
| 视频处理 | OpenCV (cv2) + FFmpeg | 任意兼容版本 |
| 实时推送 | WebSocket | FastAPI 原生支持 |
| 前端 | 原生 HTML5 + Canvas | - |

---

## 2. 系统架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                    用户浏览器                                 │
│                   (HTTP 控制经 Kong + WebSocket 结果直连)                      │
└─────────────────────────────────────────────────────────────────────────────┘
          │ HTTP API
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Kong Gateway (鉴权 + 负载均衡)                          │
└─────────────────────────────────────────────────────────────────────────────┘
          │ HTTP
          ▼
┌─────────────────────────────────────┬─────────────────────────────────────┐
│  ┌──────────────┐    ┌─────────────┐ │  ┌────────────────────────────────┐ │
│  │   RTSP摄像头  │───▶│   MediaMTX   │─┼─▶│ RT-DETR 分析服务 (FastAPI)     │ │
│  │ rtsp://xxx   │    │   RTSP 分发  │ │  │  • 视频流拉取模块 (RTSP)        │ │
│  └──────────────┘    └─────────────┘ │  │  • 抽帧模块 (全帧率)             │ │
│                                     │  │  • RT-DETR 推理模块             │ │
│                                     │  │  • 结果封装模块                 │ │
│                                     │  │  • WebSocket 推送模块           │ │
│                                     │  └────────────────────────────────┘ │
└─────────────────────────────────────┴─────────────────────────────────────┘
```

### 2.2 数据流

```
1. 控制请求
   客户端 ──HTTP──▶ Kong ──HTTP──▶ RT-DETR Service (携带 stream_url)

2. 视频流接入
   RTSP 摄像头 ──RTSP──▶ MediaMTX ──RTSP──▶ RT-DETR Service

3. 视频分析
   RTSP 流 ──▶ 解封装 ──▶ 抽帧 (全帧率) ──▶ RT-DETR 推理 ──▶ 检测结果

4. 结果推送
   检测结果 ──▶ WebSocket ──▶ 浏览器 Canvas 绘制
```

---

## 3. 组件详细设计

### 3.1 MediaMTX (协议转换服务)

#### 3.1.1 配置要求
```yaml
# conf.yaml
logLevel: info

api: yes
apiAddress: :9997

metrics: yes
metricsAddress: :9998

rtsp: yes
rtspAddress: :8554

rtmp: no
hls: no
webrtc: no
srt: no

paths:
  camera:
    source: publisher
```

#### 3.1.2 流地址
- 推流地址：`rtsp://mediamtx_ip:8554/camera`
- 拉流地址（RTSP）：`rtsp://mediamtx_ip:8554/camera`
- 推流/拉流测试建议携带 TCP 传输参数以减少丢包：`-rtsp_transport tcp`

---

### 3.2 Kong Gateway (API 网关)

Kong 仅负责控制 API 的鉴权与转发，不参与 RTSP 媒体流传输。

#### 3.2.1 插件配置
```yaml
# services/video-analysis.yaml
services:
  - name: rt-detr-service
    url: http://rt-detr-service:8080
    retries: 3
    timeout: 30000
    routes:
      - name: video-route
        paths:
          - /api/v1/video
        strip_path: false

    plugins:
      # API Key 鉴权
      - name: key-auth
        config:
          key_names:
            - api_key
          hide_credentials: false
        run_on: primary

      # 负载均衡 (如有多个后端节点)
      - name: loadbalancing
        config:
          strategy: round-robin
```

#### 3.2.2 API Key 管理
- 通过 Kong Admin API 或 Deck 管理 consumer 和 apikey
- 当前默认 key 名称为 `apikey`，推荐请求头：`apikey: <api_key>`（同时兼容 `X-API-Key`）

---

### 3.3 RT-DETR 分析服务 (FastAPI)

#### 3.3.1 模块结构
```
rt-detr-service/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口
│   ├── config.py                  # 配置管理
│   ├── models/
│   │   ├── __init__.py
│   │   └── schema.py              # Pydantic 模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── video_stream.py        # RTSP 视频流拉取
│   │   ├── frame_extractor.py     # 抽帧模块
│   │   ├── rt_detr_inference.py   # RT-DETR 推理
│   │   └── websocket_manager.py   # WebSocket 连接管理
│   └── api/
│       ├── __init__.py
│       └── endpoints.py           # API 端点
├── requirements.txt
└── Dockerfile
```

#### 3.3.2 API 端点设计

```python
# endpoints.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/video", tags=["video"])

class VideoRequest(BaseModel):
    """视频流分析请求"""
    stream_url: str              # RTSP 流地址
    api_key: str                # Kong 鉴权后传递
    enable_drawing: bool = True  # 是否返回绘图结果

class VideoResponse(BaseModel):
    """视频流分析响应"""
    session_id: str
    status: str                 # running/stopped/error
    message: str

@router.post("/start", response_model=VideoResponse)
async def start_analysis(request: VideoRequest):
    """
    启动视频流分析

    - 验证 API Key (由 Kong 注入)
    - 启动 RTSP 流拉取
    - 启动抽帧和 RT-DETR 推理
    - 建立 WebSocket 连接用于结果推送
    """
    pass

@router.post("/stop")
async def stop_analysis(session_id: str):
    """停止视频流分析"""
    pass

@router.get("/status/{session_id}")
async def get_status(session_id: str):
    """查询分析会话状态"""
    pass

# WebSocket 端点 (单独路由)
ws_router = APIRouter(prefix="/ws", tags=["websocket"])

@ws_router.websocket("/stream/{session_id}")
async def websocket_stream(websocket: WebSocket, session_id: str):
    """
    WebSocket 实时推送检测结果

    推送格式:
    {
        "type": "frame_result",
        "session_id": "xxx",
        "timestamp": 1234567890,
        "frame_index": 100,
        "detections": [
            {
                "class_id": 0,
                "class_name": "person",
                "bbox": [x1, y1, x2, y2],
                "confidence": 0.95
            }
        ],
        "annotated_frame": "<base64_encoded_jpeg>"  # 可选：标注帧
    }
    """
    pass
```

#### 3.3.3 视频流拉取模块

```python
# video_stream.py

import asyncio
import cv2
from typing import Callable, Optional
from dataclasses import dataclass

@dataclass
class VideoFrame:
    """视频帧数据结构"""
    frame: any                 # OpenCV frame
    timestamp: float          # 帧时间戳
    frame_index: int          # 帧序号

class RTSPStreamReader:
    """RTSP 流拉取器"""

    def __init__(self, stream_url: str):
        self.stream_url = stream_url
        self.cap = None
        self.running = False

    async def connect(self) -> bool:
        """连接 RTSP 流"""
        self.cap = cv2.VideoCapture(self.stream_url)
        return self.cap.isOpened()

    async def read_frame(self) -> Optional[VideoFrame]:
        """读取一帧 (同步方法在线程池执行)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._sync_read_frame
        )

    def _sync_read_frame(self) -> Optional[VideoFrame]:
        ret, frame = self.cap.read()
        if not ret:
            return None
        return VideoFrame(
            frame=frame,
            timestamp=time.time(),
            frame_index=self.frame_idx
        )

    async def stream_frames(self) -> AsyncIterator[VideoFrame]:
        """异步迭代视频帧"""
        self.running = True
        while self.running:
            frame = await self.read_frame()
            if frame is None:
                break
            yield frame
            # 控制帧率 (可选)
            await asyncio.sleep(0)  # 全帧率，不做限制

    def stop(self):
        """停止拉流"""
        self.running = False
        if self.cap:
            self.cap.release()
```

> 实现补充：
> - 运行时优先通过 `cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)` 并携带 `rtsp_transport=tcp`，降低 UDP 丢包造成的间歇中断。
> - 增加 `get_stream_info()` 返回宽、高、FPS，便于在 WebSocket 建连后向前端推送流元数据。

#### 3.3.4 RT-DETRv2 推理模块

```python
# rt_detr_inference.py

from typing import List, Dict, Any
import torch
from PIL import Image
import numpy as np

class RTDETRv2Inferencer:
    """RT-DETRv2 推理器 (COCO 80类)"""

    def __init__(self, model_path: str, device: str = "cuda"):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.model = self._load_model(model_path)
        self.model.to(self.device)
        self.model.eval()

    def _load_model(self, model_path: str):
        # RT-DETRv2 使用 ultralytics 加载
        from ultralytics import RTDETR
        return RTDETR(model_path)

    def infer(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        推理单帧图像

        Args:
            image: OpenCV BGR 格式图像

        Returns:
            检测结果列表
        """
        # 转换为 RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)

        # 推理
        results = self.model(pil_image, verbose=False)

        # 解析结果
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    detections.append({
                        "class_id": int(box.cls),
                        "class_name": result.names[int(box.cls)],
                        "bbox": box.xyxy[0].tolist(),  # [x1, y1, x2, y2]
                        "confidence": float(box.conf)
                    })

        return detections

    def draw_annotations(
        self,
        image: np.ndarray,
        detections: List[Dict[str, Any]]
    ) -> np.ndarray:
        """绘制检测框 (COCO 80类可视化)"""
        # COCO 类别颜色映射 (随机颜色或固定颜色)
        colors = {}
        for det in detections:
            if det["class_name"] not in colors:
                colors[det["class_name"]] = tuple(np.random.randint(0, 255, 3).tolist())

            x1, y1, x2, y2 = map(int, det["bbox"])
            conf = det["confidence"]
            label = f"{det['class_name']}: {conf:.2f}"
            color = colors[det["class_name"]]

            # 绘制框
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            # 绘制标签背景
            (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(image, (x1, y1 - text_h - 10), (x1 + text_w, y1), color, -1)
            # 绘制标签文字
            cv2.putText(image, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return image

    def simulate_alert(self, detection: dict):
        """简单告警模拟：控制台打印 + WebSocket 推送"""
        print(f"[ALERT] 检测到 {detection['class_name']} "
              f"置信度: {detection['confidence']:.2%}")
        # WebSocket 推送逻辑由 websocket_manager 处理
```

---

### 3.4 WebSocket 管理模块

```python
# websocket_manager.py

from fastapi import WebSocket
from typing import Dict, Set
import json
import base64
import time

class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        self.active_connections[session_id].add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_result(self, session_id: str, result: dict):
        """向指定会话的所有连接发送结果"""
        if session_id in self.active_connections:
            message = json.dumps(result)
            for connection in self.active_connections[session_id]:
                await connection.send_text(message)

    async def send_annotated_frame(
        self,
        session_id: str,
        frame: np.ndarray,
        detections: list
    ):
        """发送带标注的 Base64 编码帧"""
        # 绘制标注
        annotated = self.rt_detr.draw_annotations(frame, detections)
        # 压缩为 JPEG
        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
        # Base64 编码
        base64_frame = base64.b64encode(buffer).decode('utf-8')

        result = {
            "type": "frame_result",
            "session_id": session_id,
            "annotated_frame": base64_frame,
            "detections": detections
        }
        await self.send_result(session_id, result)

    async def send_alert(self, session_id: str, detection: dict, confidence_threshold: float = 0.5):
        """发送告警消息"""
        if detection["confidence"] < confidence_threshold:
            return

        alert = {
            "type": "alert",
            "session_id": session_id,
            "timestamp": time.time(),
            "data": {
                "class_name": detection["class_name"],
                "confidence": detection["confidence"],
                "bbox": detection["bbox"]
            }
        }
        await self.send_result(session_id, alert)
```

---

## 4. 前端设计

### 4.1 页面结构

```html
<!-- templates/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RT-DETR 实时视频分析</title>
    <style>
        #video-container {
            position: relative;
            width: 800px;
            margin: 0 auto;
        }
        #annotated-canvas {
            border: 2px solid #333;
            border-radius: 8px;
        }
        .status {
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
        }
        .status.connected { background: #d4edda; }
        .status.disconnected { background: #f8d7da; }
        .status.running { background: #cce5ff; }
        .alert-notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #ff6b6b;
            color: white;
            padding: 15px 25px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        }
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
    </style>
</head>
<body>
    <div id="status" class="status disconnected">未连接</div>
    <div id="video-container">
        <canvas id="annotated-canvas" width="800" height="600"></canvas>
    </div>

    <script>
        // WebSocket class VideoAnalyzerClient 连接管理
        {
            constructor() {
                this.ws = null;
                this.canvas = document.getElementById('annotated-canvas');
                this.ctx = this.canvas.getContext('2d');
            }

            connect(sessionId) {
                this.ws = new WebSocket(`ws://localhost:8000/ws/stream/${sessionId}`);

                this.ws.onopen = () => {
                    this.updateStatus('connected', '已连接');
                };

                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);

                    if (data.type === 'frame_result') {
                        this.renderFrame(data.annotated_frame, data.detections);
                    } else if (data.type === 'alert') {
                        // 处理告警消息
                        this.handleAlert(data.data);
                    }
                };

                this.ws.onclose = () => {
                    this.updateStatus('disconnected', '连接断开');
                };
            }

            renderFrame(base64Image, detections) {
                const img = new Image();
                img.onload = () => {
                    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
                    this.ctx.drawImage(img, 0, 0);

                    // 绘制检测信息
                    this.ctx.fillStyle = '#00ff00';
                    this.ctx.font = '14px Arial';
                    this.ctx.fillText(`检测目标: ${detections.length} 个`, 10, 25);
                };
                img.src = 'data:image/jpeg;base64,' + base64Image;
            }

            updateStatus(className, text) {
                const el = document.getElementById('status');
                el.className = `status ${className}`;
                el.textContent = text;
            }

            handleAlert(alertData) {
                // 简单告警模拟：控制台打印 + 页面提示
                console.log(`[ALERT] 检测到 ${alertData.class_name} ` +
                            `置信度: ${(alertData.confidence * 100).toFixed(1)}%`);

                // 页面显示告警通知
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert-notification';
                alertDiv.innerHTML = `⚠️ 检测到 <strong>${alertData.class_name}</strong> ` +
                                    `(置信度: ${(alertData.confidence * 100).toFixed(1)}%)`;
                document.body.appendChild(alertDiv);

                // 3秒后移除
                setTimeout(() => alertDiv.remove(), 3000);
            }
        }
    </script>
</body>
</html>
```

---

## 5. 部署架构

### 5.1 Docker Compose 编排

```yaml
# docker-compose.yml
version: '3.8'

services:
  mediamtx:
    image: aler9/mediamtx:latest
    container_name: mediamtx
    ports:
      - "8554:8554"   # RTSP
    volumes:
      - ./mediamtx/conf.yaml:/mediamtx/conf.yaml
    restart: unless-stopped

  kong-gateway:
    image: kong:latest
    container_name: kong
    ports:
      - "8000:8000"   # Kong Proxy
      - "8443:8443"   # Kong Proxy HTTPS
      - "8001:8001"   # Kong Admin
    environment:
      - KONG_DATABASE=off
      - KONG_DECLARATIVE_CONFIG=/kong/kong.yml
    volumes:
      - ./kong/kong.yml:/kong/kong.yml:ro
    depends_on:
      - mediamtx
    restart: unless-stopped

  rt-detr-service:
    build:
      context: ./rt-detr-service
      dockerfile: Dockerfile
    container_name: rt-detr-service
    ports:
      - "8080:8080"
    environment:
      - MODEL_PATH=/models/rt-detr.pt
      - DEVICE=cuda
    volumes:
      - ./models:/models:ro
    depends_on:
      - kong-gateway
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

networks:
  default:
    name: video-analysis-network

### 5.2 长时间推流测试（本地）

- 使用本地样例视频 `BigBuckBunny.mp4` 进行长时间推流，可通过 FFmpeg 循环方式避免视频过短导致的中断：
  ```bash
  ffmpeg -re -stream_loop -1 -i BigBuckBunny.mp4 -c copy -f rtsp -rtsp_transport tcp rtsp://localhost:8554/camera
  ```
- `-stream_loop -1` 表示无限循环；`-rtsp_transport tcp` 可减少网络抖动；推流进程可放后台以便持续为 RT-DETR 服务提供输入。
```

---

## 6. 环境要求

### 6.1 硬件要求
| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 4 核 | 8 核+ |
| 内存 | 8 GB | 16 GB+ |
| GPU | NVIDIA GPU (RTX 2060+) | RTX 3060+ |
| 硬盘 | 20 GB | 50 GB+ |

### 6.2 软件要求
- Docker >= 20.10
- Docker Compose >= 2.0
- NVIDIA Docker Runtime (如需 GPU 支持)
- 有效 RTSP 视频流源

---

## 7. API 文档

### 7.1 启动分析

`stream_url` 需由 RT-DETR 直接访问（不经过 Kong）。

**Endpoint:** `POST /api/v1/video/start`

**Request:**
```json
{
    "stream_url": "rtsp://mediamtx:8554/camera",
    "enable_drawing": true
}
```

**Response:**
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "message": "Analysis started successfully"
}
```

### 7.2 停止分析

**Endpoint:** `POST /api/v1/video/stop`

**Request:**
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```json
{
    "status": "stopped",
    "message": "Analysis stopped"
}
```

### 7.3 WebSocket 消息格式

**客户端发送 (可选):**
```json
{
    "type": "control",
    "action": "pause"  // pause/resume/stop
}
```

**服务端推送:**
```json
{
    "type": "frame_result",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": 1699939200.123,
    "frame_index": 150,
    "detections": [
        {
            "class_id": 0,
            "class_name": "person",
            "bbox": [100, 200, 300, 500],
            "confidence": 0.95
        }
    ],
    "annotated_frame": "/9j/4AAQSkZJRgABAQEAYABgAAD..."
}
```

---

## 8. 安全考虑

### 8.1 Kong 安全配置
- 启用 API Key 认证
- 配置速率限制
- 启用 HTTPS
- 配置 CORS

### 8.2 网络隔离
- 生产环境使用内部网络
- 不暴露 MediaMTX RTSP 端口到公网
- Kong 仅暴露必要端口

---

## 9. 性能优化

### 9.1 优化建议
1. **GPU 利用率**: 确保 RT-DETR 模型在 GPU 上运行
2. **内存管理**: 及时释放视频帧内存
3. **并发处理**: 如需处理多路视频，使用多进程
4. **帧率控制**: 根据 GPU 性能调整处理帧率
5. **JPEG 质量**: 降低 Base64 编码质量以减少带宽

---

## 10. 目录结构

```
kong-poc/
├── README.md
├── Makefile
├── docker-compose.yml
│
├── mediamtx/
│   └── conf.yaml
│
├── kong/
│   └── kong.yml
│
├── rt-detr-service/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── schema.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── video_stream.py
│   │   │   ├── frame_extractor.py
│   │   │   ├── rt_detr_inference.py
│   │   │   └── websocket_manager.py
│   │   └── api/
│   │       ├── __init__.py
│   │       └── endpoints.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── templates/
│       └── index.html
│
└── models/
    └── rt-detr.pt
```

---

## 11. 项目配置确认

| 配置项 | 值 |
|--------|-----|
| RT-DETR 模型 | RT-DETRv2 |
| 检测类别 | COCO 80类 |
| 录制功能 | 无 |
| 告警方式 | 控制台日志 + WebSocket 推送（模拟） |

---

## 12. 目录结构
