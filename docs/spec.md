# 边缘视频分析与 LLM 网关系统技术规范

## 1. 概述

### 1.1 目标
构建一个统一的边缘推理与网关管理 PoC，包含 RTSP 实时视频分析（RT-DETRv2）与 LLM API 服务（Mock LLM、vLLM）。Kong 负责鉴权、限流、路由与 CORS，视频媒体流由 MediaMTX 处理并供 RT-DETR 服务消费。

### 1.2 技术栈
| 组件 | 技术选型 | 说明 |
|------|----------|------|
| 网关 | Kong Gateway 3.6 | Key-Auth、限流、CORS、声明式配置 |
| 协议转换 | MediaMTX | RTSP 入流、WebRTC 出流 |
| 视频分析 | FastAPI + RT-DETRv2 | RTSP 拉流、抽帧推理、WebSocket 推送 |
| LLM 模拟 | FastAPI | OpenAI 兼容 Chat Completions（SSE） |
| 推理引擎 | vLLM | 真实模型服务（可选） |
| 容器化 | Docker + Compose | 统一编排 |

---

## 2. 系统架构

### 2.1 架构图

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

### 2.2 数据流

1. 控制请求
   客户端 -> Kong -> RT-DETR Service (携带 API Key)
2. 视频流接入
   摄像头 -> MediaMTX (RTSP) -> RT-DETR Service
3. 推理与推送
   抽帧 -> RT-DETR 推理 -> WebSocket 推送结果
4. LLM 请求
   客户端 -> Kong -> Mock LLM / vLLM

---

## 3. 组件设计

### 3.1 Kong Gateway

- 配置文件: `kong/kong.yml`
- 服务与路由:
  - `/api/v1/video` -> RT-DETR 控制 API
  - `/ws` -> RT-DETR WebSocket
  - `/` -> RT-DETR 前端页面
  - `/v1/chat/completions` -> Mock LLM
  - `/v2/chat/completions` -> vLLM
- 插件:
  - `key-auth`: 统一鉴权
  - `rate-limiting`: 按分钟限流
  - `request-size-limiting`: 视频控制 API 请求体限制
  - `cors`: 跨域支持

### 3.2 MediaMTX (RTSP / WebRTC)

- 配置文件: `mediamtx/mediamtx.yml`
- RTSP 端口: `8554`
- WebRTC 端口: `8889`
- 典型地址:
  - RTSP: `rtsp://localhost:8554/camera`
  - WHEP: `http://localhost:8889/camera/whep`

### 3.3 RT-DETR 视频分析服务

- 服务目录: `upstream/rt-detr`
- 主要能力:
  - RTSP 拉流（OpenCV + CAP_FFMPEG）
  - RT-DETRv2 推理
  - 帧编码（Base64 JPEG）
  - WebSocket 推送与告警
  - 简易前端页面

#### 3.3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/video/start` | 启动分析会话 |
| POST | `/api/v1/video/stop` | 停止分析会话 |
| GET  | `/api/v1/video/sessions` | 列出会话 |
| GET  | `/api/v1/video/sessions/{session_id}` | 会话详情 |
| GET  | `/api/v1/video/health` | 健康检查 |

#### 3.3.2 WebSocket

- 地址: `ws://localhost:8000/ws/stream/{session_id}`
- 服务端消息类型:
  - `stream_info`: 流元数据（宽高、FPS）
  - `status`: 会话状态变更
  - `frame_result`: 帧推理结果
  - `alert`: 告警信息
  - `error`: 错误信息

#### 3.3.3 模型与配置

- 模型文件: `models/rt-detr.pt`
- 主要环境变量:
  - `RT_DETR_MODEL_PATH`
  - `RT_DETR_DEVICE`
  - `RT_DETR_DEBUG`
  - `RT_DETR_CONFIDENCE_THRESHOLD`
  - `RT_DETR_ALERT_ENABLED`
  - `RT_DETR_ALERT_CONFIDENCE_THRESHOLD`
  - `RT_DETR_FRAME_QUALITY`
  - `RT_DETR_MAX_FRAME_WIDTH`

### 3.4 Mock LLM

- 服务目录: `upstream/mock-llm`
- 接口: `POST /v1/chat/completions`
- 特性:
  - OpenAI 兼容格式
  - 支持 `stream: true` (SSE)
  - 支持 `ttft_ms` 模拟首 token 延迟

### 3.5 vLLM

- 服务目录: `upstream/vllm`
- 接口: `POST /v2/chat/completions`
- 说明: 依赖本地预编译 venv 与模型配置（按需启用）

---

## 4. API 设计

### 4.1 视频分析请求示例

```json
POST /api/v1/video/start
{
  "stream_url": "rtsp://mediamtx:8554/camera",
  "enable_drawing": true
}
```

OpenAPI 3.0 模版（示例）

```yaml
openapi: 3.0.3
info:
  title: Video Analysis API
  version: 1.0.0
paths:
  /api/v1/video/start:
    post:
      summary: Start video analysis session
      tags:
        - video
      security:
        - ApiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - stream_url
              properties:
                stream_url:
                  type: string
                  example: rtsp://mediamtx:8554/camera
                enable_drawing:
                  type: boolean
                  default: true
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  session_id:
                    type: string
                  status:
                    type: string
                  message:
                    type: string
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: apikey
```

Postman v2.1 模版（示例）

```json
{
  "name": "Start Video Analysis",
  "request": {
    "method": "POST",
    "header": [
      {"key": "Content-Type", "value": "application/json"},
      {"key": "apikey", "value": "video-api-key-001"}
    ],
    "body": {
      "mode": "raw",
      "raw": "{\n  \"stream_url\": \"rtsp://mediamtx:8554/camera\",\n  \"enable_drawing\": true\n}"
    },
    "url": {
      "raw": "http://localhost:8000/api/v1/video/start",
      "protocol": "http",
      "host": ["localhost"],
      "port": "8000",
      "path": ["api", "v1", "video", "start"]
    }
  }
}
```

### 4.1.1 停止分析（/api/v1/video/stop）

OpenAPI 3.0 模版（示例）

```yaml
openapi: 3.0.3
info:
  title: Video Analysis API
  version: 1.0.0
paths:
  /api/v1/video/stop:
    post:
      summary: Stop video analysis session
      tags:
        - video
      security:
        - ApiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - session_id
              properties:
                session_id:
                  type: string
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  session_id:
                    type: string
                  status:
                    type: string
                  message:
                    type: string
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: apikey
```

Postman v2.1 模版（示例）

```json
{
  "name": "Stop Video Analysis",
  "request": {
    "method": "POST",
    "header": [
      {"key": "Content-Type", "value": "application/json"},
      {"key": "apikey", "value": "video-api-key-001"}
    ],
    "body": {
      "mode": "raw",
      "raw": "{\n  \"session_id\": \"550e8400-e29b-41d4-a716-446655440000\"\n}"
    },
    "url": {
      "raw": "http://localhost:8000/api/v1/video/stop",
      "protocol": "http",
      "host": ["localhost"],
      "port": "8000",
      "path": ["api", "v1", "video", "stop"]
    }
  }
}
```

### 4.1.2 列出会话（/api/v1/video/sessions）

OpenAPI 3.0 模版（示例）

```yaml
openapi: 3.0.3
info:
  title: Video Analysis API
  version: 1.0.0
paths:
  /api/v1/video/sessions:
    get:
      summary: List active sessions
      tags:
        - video
      security:
        - ApiKeyAuth: []
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
                  properties:
                    session_id:
                      type: string
                    status:
                      type: string
                    frame_count:
                      type: integer
                    stream_url:
                      type: string
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: apikey
```

Postman v2.1 模版（示例）

```json
{
  "name": "List Video Sessions",
  "request": {
    "method": "GET",
    "header": [
      {"key": "apikey", "value": "video-api-key-001"}
    ],
    "url": {
      "raw": "http://localhost:8000/api/v1/video/sessions",
      "protocol": "http",
      "host": ["localhost"],
      "port": "8000",
      "path": ["api", "v1", "video", "sessions"]
    }
  }
}
```

### 4.1.3 会话详情（/api/v1/video/sessions/{session_id}）

OpenAPI 3.0 模版（示例）

```yaml
openapi: 3.0.3
info:
  title: Video Analysis API
  version: 1.0.0
paths:
  /api/v1/video/sessions/{session_id}:
    get:
      summary: Get session details
      tags:
        - video
      security:
        - ApiKeyAuth: []
      parameters:
        - name: session_id
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  session_id:
                    type: string
                  status:
                    type: string
                  frame_count:
                    type: integer
                  stream_url:
                    type: string
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: apikey
```

Postman v2.1 模版（示例）

```json
{
  "name": "Get Video Session",
  "request": {
    "method": "GET",
    "header": [
      {"key": "apikey", "value": "video-api-key-001"}
    ],
    "url": {
      "raw": "http://localhost:8000/api/v1/video/sessions/550e8400-e29b-41d4-a716-446655440000",
      "protocol": "http",
      "host": ["localhost"],
      "port": "8000",
      "path": ["api", "v1", "video", "sessions", "550e8400-e29b-41d4-a716-446655440000"]
    }
  }
}
```

### 4.1.4 健康检查（/api/v1/video/health）

OpenAPI 3.0 模版（示例）

```yaml
openapi: 3.0.3
info:
  title: Video Analysis API
  version: 1.0.0
paths:
  /api/v1/video/health:
    get:
      summary: Health check
      tags:
        - video
      security:
        - ApiKeyAuth: []
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                  model_loaded:
                    type: boolean
                  gpu_available:
                    type: boolean
                  uptime_seconds:
                    type: number
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: apikey
```

Postman v2.1 模版（示例）

```json
{
  "name": "Video Health",
  "request": {
    "method": "GET",
    "header": [
      {"key": "apikey", "value": "video-api-key-001"}
    ],
    "url": {
      "raw": "http://localhost:8000/api/v1/video/health",
      "protocol": "http",
      "host": ["localhost"],
      "port": "8000",
      "path": ["api", "v1", "video", "health"]
    }
  }
}
```

### 4.2 WebSocket 推送示例

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

### 4.3 LLM 请求示例

```json
POST /v1/chat/completions
{
  "model": "mock-llm",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": true
}
```

OpenAPI 3.0 模版（示例）

```yaml
openapi: 3.0.3
info:
  title: LLM Chat Completions
  version: 1.0.0
paths:
  /v1/chat/completions:
    post:
      summary: Create chat completion (Mock LLM)
      tags:
        - llm
      security:
        - ApiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - messages
              properties:
                model:
                  type: string
                  example: mock-llm
                messages:
                  type: array
                  items:
                    type: object
                    properties:
                      role:
                        type: string
                      content:
                        type: string
                stream:
                  type: boolean
                  default: false
                ttft_ms:
                  type: integer
                  description: Delay before first token in ms
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: apikey
```

Postman v2.1 模版（示例）

```json
{
  "name": "Mock LLM Chat Completions",
  "request": {
    "method": "POST",
    "header": [
      {"key": "Content-Type", "value": "application/json"},
      {"key": "apikey", "value": "llm-api-key-001"}
    ],
    "body": {
      "mode": "raw",
      "raw": "{\n  \"model\": \"mock-llm\",\n  \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}],\n  \"stream\": true\n}"
    },
    "url": {
      "raw": "http://localhost:8000/v1/chat/completions",
      "protocol": "http",
      "host": ["localhost"],
      "port": "8000",
      "path": ["v1", "chat", "completions"]
    }
  }
}
```

### 4.4 vLLM Chat Completions（/v2/chat/completions）

OpenAPI 3.0 模版（示例）

```yaml
openapi: 3.0.3
info:
  title: vLLM Chat Completions
  version: 1.0.0
paths:
  /v2/chat/completions:
    post:
      summary: Create chat completion (vLLM)
      tags:
        - llm
      security:
        - ApiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - messages
              properties:
                model:
                  type: string
                  example: your-model
                messages:
                  type: array
                  items:
                    type: object
                    properties:
                      role:
                        type: string
                      content:
                        type: string
                stream:
                  type: boolean
                  default: false
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: apikey
```

Postman v2.1 模版（示例）

```json
{
  "name": "vLLM Chat Completions",
  "request": {
    "method": "POST",
    "header": [
      {"key": "Content-Type", "value": "application/json"},
      {"key": "apikey", "value": "llm-api-key-001"}
    ],
    "body": {
      "mode": "raw",
      "raw": "{\n  \"model\": \"your-model\",\n  \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]\n}"
    },
    "url": {
      "raw": "http://localhost:8000/v2/chat/completions",
      "protocol": "http",
      "host": ["localhost"],
      "port": "8000",
      "path": ["v2", "chat", "completions"]
    }
  }
}
```

---

## 5. 部署架构

### 5.1 Docker Compose

- 编排文件: `docker-compose.yml`
- 关键端口:
  - Kong: 8000/8443 (Proxy), 8001/8444 (Admin)
  - MediaMTX: 8554 (RTSP), 8889 (WebRTC), 9997 (API), 9998 (Metrics)
  - RT-DETR: 8081 (直连调试)
  - Mock LLM: 8082 (直连调试)
  - vLLM: 8083 (直连调试)

### 5.2 GPU 支持

- RT-DETR 与 vLLM 可使用 GPU（Compose 中已声明 NVIDIA 设备）

---

## 6. 安全与治理

- API Key 鉴权：`kong/kong.yml`
  - 视频分析：`video-api-key-001`
  - LLM：`llm-api-key-001`
- 统一请求头：`apikey: <key>`
- 速率限制：按分钟控制（示例配置）
- 请求体限制：视频控制接口最大 1 MB
- CORS：允许跨域访问（PoC 环境）

---

## 7. 运行与验证

### 7.1 启动

```bash
docker-compose up -d
```

### 7.2 推流测试

```bash
ffmpeg -re -stream_loop -1 -i BigBuckBunny.mp4 -c copy -f rtsp -rtsp_transport tcp rtsp://localhost:8554/camera
```

### 7.3 调试入口

- 前端（经 Kong）：http://localhost:8000/
- RT-DETR 健康检查：http://localhost:8000/api/v1/video/health

---

## 8. 目录结构

```
kong-poc/
├── README.md
├── docker-compose.yml
├── docs/
│   ├── spec.md
│   ├── openapi.yaml           # OpenAPI 3.0 规范
│   └── postman_collection.json # Postman Collection v2.1
├── kong/                 # Kong 配置
├── mediamtx/             # MediaMTX 配置与 WebRTC 工具页
├── upstream/
│   ├── rt-detr/          # RT-DETR 视频分析服务
│   ├── mock-llm/         # Mock LLM 服务
│   └── vllm/             # vLLM 服务
├── models/               # 模型文件
└── scripts/              # 测试脚本
```

---

## 9. API 文档与导入

- OpenAPI 规范: `docs/openapi.yaml`
- Postman 集合: `docs/postman_collection.json`
