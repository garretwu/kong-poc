# RT-DETR Video Analysis Service

实时视频流分析服务，基于 RT-DETRv2 模型，支持 COCO 80类目标检测。

## 特性

- **实时分析**: 支持 FLV/HTTP/RTSP 视频流
- **RT-DETRv2**: 使用最新 RT-DETRv2 模型进行目标检测
- **WebSocket 推送**: 实时推送检测结果和告警到浏览器
- **API 集成**: 通过 Kong Gateway 提供 API Key 认证
- **可视化界面**: 简洁的前端界面，实时显示检测结果

## 快速开始

### 1. 准备模型文件

下载 RT-DETRv2 模型文件到 `models/` 目录：

```bash
# 示例：下载 RT-DETR-L 模型
wget https://github.com/ultralytics/assets/releases/download/v8.2.0/rtdetr-l.pt -O models/rt-detr.pt
```

### 2. 启动服务

使用 Docker Compose 启动所有服务：

```bash
docker-compose up -d
```

### 3. 访问服务

- **前端界面**: http://localhost:8000
- **API 健康检查**: http://localhost:8000/api/v1/video/health

### 4. 测试推流

需要向 MediaMTX 推送 RTSP 流：

```bash
# 使用 FFmpeg 推送测试视频
ffmpeg -re -i test.mp4 -c copy -f rtsp -rtsp_transport tcp rtsp://localhost:8554/camera
```

## API 文档

### 启动分析

```bash
POST /api/v1/video/start
Content-Type: application/json

{
    "stream_url": "http://mediamtx:8080/camera.flv",
    "enable_drawing": true
}
```

响应:
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "message": "Analysis started successfully"
}
```

### 停止分析

```bash
POST /api/v1/video/stop
Content-Type: application/json

{
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### WebSocket 连接

```
ws://localhost:8000/ws/stream/{session_id}
```

推送消息格式:
```json
{
    "type": "frame_result",
    "session_id": "xxx",
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

告警消息:
```json
{
    "type": "alert",
    "session_id": "xxx",
    "timestamp": 1699939200.123,
    "data": {
        "class_name": "person",
        "confidence": 0.95,
        "bbox": [100, 200, 300, 500]
    }
}
```

## 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RT_DETR_MODEL_PATH` | `/models/rt-detr.pt` | 模型文件路径 |
| `RT_DETR_DEVICE` | `cuda` | 运行设备 (cuda/cpu) |
| `RT_DETR_CONFIDENCE_THRESHOLD` | `0.5` | 检测置信度阈值 |
| `RT_DETR_ALERT_ENABLED` | `true` | 是否启用告警 |
| `RT_DETR_ALERT_CONFIDENCE_THRESHOLD` | `0.7` | 告警置信度阈值 |

### Kong API Key

默认 API Key: `kong-api-key-video-2024`

使用示例:
```bash
curl -H "X-API-Key: kong-api-key-video-2024" \
     http://localhost:8000/api/v1/video/health
```

## 目录结构

```
rt-detr/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置管理
│   ├── api/
│   │   ├── __init__.py
│   │   └── endpoints.py        # API 端点
│   ├── models/
│   │   ├── __init__.py
│   │   └── schema.py           # Pydantic 模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── rt_detr_inference.py  # RT-DETR 推理
│   │   ├── video_stream.py       # 视频流拉取
│   │   └── websocket_manager.py  # WebSocket 管理
│   └── templates/
│       └── index.html          # 前端页面
├── Dockerfile
└── requirements.txt
```

## 开发

### 本地运行

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行服务
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 测试

```bash
pytest tests/
```

## 依赖

- Python 3.11+
- FastAPI >= 0.100
- Ultralytics (RT-DETR)
- OpenCV
- PyTorch
