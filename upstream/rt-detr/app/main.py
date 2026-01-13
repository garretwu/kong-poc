"""
RT-DETR 视频分析服务主入口
"""

import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router, frontend_router
from app.services.websocket_manager import connection_manager
from app.config import settings


# 启动时间追踪
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global _start_time
    _start_time = time.time()

    # 启动时初始化
    print(f"RT-DETR Service starting on {settings.host}:{settings.port}")
    print(f"Model path: {settings.model_path}")
    print(f"Device: {settings.device}")

    yield

    # 关闭时清理
    print("RT-DETR Service shutting down...")


# 创建 FastAPI 应用
app = FastAPI(
    title="RT-DETR Video Analysis Service",
    description="实时视频流分析服务，支持 RT-DETRv2 模型推理",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 中间配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)
app.include_router(frontend_router)


# WebSocket 端点
from fastapi import WebSocket, WebSocketDisconnect


@app.websocket("/ws/stream/{session_id}")
async def websocket_stream(websocket: WebSocket, session_id: str):
    """WebSocket 实时视频流

    Args:
        websocket: WebSocket 连接
        session_id: 会话 ID
    """
    session = await connection_manager.connect(session_id, websocket)

    try:
        # 等待消息
        while True:
            try:
                data = await websocket.receive_text()
                # 解析控制消息
                import json
                message = json.loads(data)

                if message.get("type") == "control":
                    action = message.get("action")
                    if action == "stop":
                        connection_manager.update_session_status(
                            session_id, "stopped"
                        )
                        break
                    elif action == "ping":
                        await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                pass

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        connection_manager.disconnect(session_id, websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
