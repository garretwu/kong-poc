# kong-poc

Kong API网关与LLM服务集成的概念验证项目，展示如何在边缘推理场景中使用Kong管理和保护LLM API。

## 核心架构

```
客户端 → Kong网关(8000端口) → Mock LLM服务(8000内部/9000外部)
         ↓ 认证、速率限制、CORS
```

## 目录结构

```
kong-poc/
├── README.md                          # 项目说明文档
├── kong/                              # Kong网关配置目录
│   ├── kong.yaml                      # Kong声明式配置文件
│   └── docker-compose.yaml            # 容器编排配置
├── upstream/                          # 上游服务目录
│   └── mock-llm/                      # Mock LLM服务
│       ├── Dockerfile                 # 容器镜像定义
│       ├── app.py                     # FastAPI应用
│       ├── requirements.txt           # Python依赖
│       └── __pycache__/               # Python缓存目录
├── scripts/                           # 测试脚本目录
│   ├── test_stream_abort.sh           # 流中止测试脚本
│   └── test_timeout.sh                # 超时测试脚本
└── .venv/                             # Python虚拟环境
```

## 主要组件

### 1. Mock LLM服务 (`upstream/mock-llm/app.py`)

基于FastAPI实现的OpenAI兼容Chat Completions API：

- **端点**:
  - `POST /v1/chat/completions` - 聊天完成请求（支持流式和非流式）
  - `GET /healthz` - 健康检查
- **功能**:
  - 流式响应（Server-Sent Events格式）
  - 可配置的首个token到达时间延迟 (ttft_ms)
  - 模拟token计数和计费信息
  - 支持temperature和max_tokens参数
  - 客户端断开连接检测

### 2. Kong网关配置 (`kong/kong.yaml`)

声明式配置包含：

- **服务**: llm-service (指向 http://mock-llm:8000)
- **路由**: `/v1/chat/completions` POST请求
- **插件**:
  - **key-auth**: API密钥认证 (x-api-key请求头)
  - **rate-limiting**: 速率限制（5请求/秒，100请求/分钟）
  - **cors**: CORS支持（允许所有源）
- **消费者**: demo-client (API密钥: demo-key)

### 3. 容器编排 (`kong/docker-compose.yaml`)

双容器部署架构：

- **mock-llm**: Mock LLM服务
  - 内部端口: 8000
  - 外部端口: 9000
- **kong**: Kong网关 (版本 3.6)
  - 代理端口: 8000
  - 管理API端口: 8001
  - 无数据库模式（声明式配置）
- **网络**: kong-net (共享网络)

### 4. 测试脚本 (`scripts/`)

#### `test_stream_abort.sh` - 流中止测试
- 发送流式聊天完成请求到Kong
- 在指定延迟后中止连接
- 验证Mock LLM是否正确检测客户端断开

#### `test_timeout.sh` - 超时测试
- 测试Kong网关的上游超时处理
- 测试场景：
  - 短延迟请求（应返回200）
  - 长延迟请求（应返回Kong 504网关超时）
  - 流式和非流式两种模式

## 技术栈

| 组件 | 技术 |
|------|------|
| 网关 | Kong 3.6 |
| 后端 | Python 3.11 + FastAPI 0.110.0 |
| ASGI服务器 | Uvicorn 0.29.0 |
| 容器化 | Docker + Docker Compose 3.9 |
| API风格 | REST + Server-Sent Events (SSE) |

## 主要功能

- ✓ API网关代理与负载管理
- ✓ 基于密钥的API认证
- ✓ 速率限制防滥用
- ✓ OpenAI兼容的Chat Completions接口
- ✓ SSE流式响应支持
- ✓ 超时和连接管理测试

## 快速开始

### 启动服务

```bash
cd kong
docker-compose up -d
```

### 测试API

使用curl测试（通过Kong网关）：

```bash
# 非流式请求
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-api-key: demo-key" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# 流式请求
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-api-key: demo-key" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

### 运行测试脚本

```bash
# 测试流式连接中止
cd scripts
./test_stream_abort.sh

# 测试超时行为
./test_timeout.sh
```

## Kong配置说明

### 环境变量

```
KONG_DATABASE: "off"                                    # 无数据库模式
KONG_DECLARATIVE_CONFIG: /kong/declarative/kong.yaml   # 配置文件路径
KONG_PROXY_LISTEN: "0.0.0.0:8000"                      # 代理监听地址
KONG_ADMIN_LISTEN: "0.0.0.0:8001"                      # 管理API监听地址
```

### 认证

默认API密钥：
- 消费者: demo-client
- API Key: demo-key
- 使用方式: 在请求头中添加 `x-api-key: demo-key`

### 速率限制

- 每秒限制: 5请求
- 每分钟限制: 100请求

## 使用场景

- 在边缘计算环境中部署LLM推理服务
- 使用Kong网关管理和保护LLM API
- 测试LLM流式响应的连接管理和超时行为
- API网关功能验证（认证、速率限制、CORS等）

## 项目状态

目前处于概念验证阶段，包含完整的最小可用配置（MVP），适合用于测试Kong网关在LLM服务场景下的各种特性和行为。
