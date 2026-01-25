# kong-poc

Kong 网关驱动的边缘推理与视频分析概念验证项目。该项目将 RTSP 实时视频分析（RT-DETRv2）与 LLM API（Mock LLM 与 vLLM）统一纳入 Kong 进行鉴权、限流与路由管理，并提供前端与 WebSocket 实时推送能力。

## 核心架构

```
视频链路:
RTSP 摄像头 -> MediaMTX -> RT-DETR 服务 -> WebSocket -> 浏览器
     |              ^
     |              |
     +-- 控制 API 通过 Kong 访问 /api/v1/video

LLM 链路:
客户端 -> Kong -> Mock LLM (/v1/chat/completions)
                 -> vLLM (/v2/chat/completions)
```

## 主要组件

- Kong Gateway: 统一鉴权、限流、CORS、请求大小限制与路由转发（`kong/kong.yml`）
- MediaMTX: RTSP 接入与 WebRTC 出流（`mediamtx/mediamtx.yml`）
- RT-DETR 视频分析服务: RTSP 拉流 + 抽帧推理 + WebSocket 推送 + 简易前端（`upstream/rt-detr`）
- Mock LLM: OpenAI 兼容 Chat Completions（SSE 流式/非流式）（`upstream/mock-llm`）
- vLLM: 真实模型服务接入（`upstream/vllm`）

## 快速开始

### 1. 准备 RT-DETR 模型

```bash
wget https://github.com/ultralytics/assets/releases/download/v8.2.0/rtdetr-l.pt -O models/rt-detr.pt
```

### 2. 启动服务

```bash
docker-compose up -d
```

### 3. 推送 RTSP 流（示例）

```bash
ffmpeg -re -stream_loop -1 -i BigBuckBunny.mp4 -c copy -f rtsp -rtsp_transport tcp rtsp://localhost:8554/camera
```

### 4. 访问前端

- 视频分析前端（通过 Kong）：http://localhost:8000/
- RT-DETR 健康检查：http://localhost:8000/api/v1/video/health

## API 快速测试

### 视频分析

```bash
curl -X POST http://localhost:8000/api/v1/video/start \
  -H "Content-Type: application/json" \
  -H "apikey: video-api-key-001" \
  -d '{
    "stream_url": "rtsp://mediamtx:8554/camera",
    "enable_drawing": true
  }'
```

### Mock LLM

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "apikey: llm-api-key-001" \
  -d '{
    "model": "mock-llm",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

### vLLM（如已配置）

```bash
curl -X POST http://localhost:8000/v2/chat/completions \
  -H "Content-Type: application/json" \
  -H "apikey: llm-api-key-001" \
  -d '{
    "model": "your-model",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## 认证与路由

- API Key 由 `kong/kong.yml` 定义
  - 视频分析：`video-api-key-001`
  - LLM：`llm-api-key-001`
- 请求头使用 `apikey: <key>`

## 端口一览

- Kong Proxy: `8000` (HTTP), `8443` (HTTPS)
- Kong Admin: `8001` (HTTP), `8444` (HTTPS)
- MediaMTX: `8554` (RTSP), `8889` (WebRTC HTTP), `9997` (API), `9998` (Metrics)
- RT-DETR: `8081` (直连调试)
- Mock LLM: `8082` (直连调试)
- vLLM: `8083` (直连调试)

## 目录结构

```
kong-poc/
├── README.md
├── docker-compose.yml
├── kong/                     # Kong 配置
├── mediamtx/                 # MediaMTX 配置与 WebRTC 工具页
├── upstream/
│   ├── rt-detr/              # RT-DETR 视频分析服务
│   ├── mock-llm/             # Mock LLM
│   └── vllm/                 # vLLM 接入
├── models/                   # 模型文件
└── scripts/                  # 测试脚本
```

## 备注

- vLLM 服务在 `docker-compose.yml` 中依赖本地 venv 路径，请按需调整或注释。
- MediaMTX WebRTC 测试页位于 `mediamtx/webrtc.html`，可用于本地播放调试。
