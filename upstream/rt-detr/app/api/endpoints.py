"""
API 端点
"""

import asyncio
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse

from app.models.schema import (
    VideoRequest,
    VideoResponse,
    VideoStopRequest,
    SessionInfo,
    HealthResponse
)
from app.services.websocket_manager import connection_manager, SessionStatus
from app.services.video_stream import create_stream_reader, VideoStreamError
from app.services.rt_detr_inference import RTDETRv2Inferencer
from app.config import settings


router = APIRouter(prefix="/api/v1/video", tags=["video"])
TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "templates" / "index.html"

# 全局推理器实例
_inferencer: Optional[RTDETRv2Inferencer] = None
_analysis_tasks: dict = {}


def get_inferencer() -> RTDETRv2Inferencer:
    """获取推理器单例"""
    global _inferencer
    if _inferencer is None:
        _inferencer = RTDETRv2Inferencer(
            model_path=settings.model_path,
            device=settings.device,
            confidence_threshold=settings.confidence_threshold
        )
    return _inferencer


async def run_analysis(session_id: str, stream_url: str):
    """运行视频分析任务

    Args:
        session_id: 会话 ID
        stream_url: 流地址
    """
    print(f"[run_analysis] start session={session_id} url={stream_url}")
    inferencer = get_inferencer()
    stream_reader = create_stream_reader(stream_url)

    try:
        # 更新会话状态
        connection_manager.update_session_status(session_id, SessionStatus.RUNNING)
        await connection_manager.send_status(session_id, SessionStatus.RUNNING.value, "Analysis started")

        # 连接视频流
        if not stream_reader.connect():
            print(f"[run_analysis] connect failed session={session_id}")
            await connection_manager.send_error(
                session_id,
                "Failed to connect to video stream"
            )
            return
        else:
            print(f"[run_analysis] connect ok session={session_id}")

        # 发送流信息
        stream_info = stream_reader.get_stream_info()
        if stream_info:
            await connection_manager.send_json(
                session_id,
                {
                    "type": "stream_info",
                    "session_id": session_id,
                    "info": stream_info
                }
            )

        # 异步迭代帧
        async for frame in stream_reader.stream_frames():
            # RT-DETR 推理
            detections = inferencer.infer(frame.frame)
            if frame.frame_index % 10 == 0:
                print(f"[run_analysis] frame {frame.frame_index} det={len(detections)}")

            # 绘制标注
            if settings.frame_quality > 0:
                annotated = inferencer.draw_annotations(frame.frame.copy(), detections)
                # 调整大小
                from app.services.websocket_manager import frame_encoder
                annotated = frame_encoder.resize(annotated, settings.max_frame_width)
                # 编码
                base64_frame = frame_encoder.encode_jpeg(annotated, settings.frame_quality)
            else:
                base64_frame = None

            # 发送结果
            await connection_manager.send_frame_result(
                session_id=session_id,
                base64_frame=base64_frame,
                detections=detections,
                timestamp=frame.timestamp,
                frame_index=frame.frame_index
            )

            # 告警处理
            if settings.alert_enabled:
                for detection in detections:
                    await connection_manager.send_alert(
                        session_id,
                        detection,
                        settings.alert_confidence_threshold
                    )

    except Exception as e:
        print(f"[run_analysis] error session={session_id} err={e}")
        await connection_manager.send_error(session_id, str(e))
    finally:
        stream_reader.stop()
        connection_manager.update_session_status(session_id, SessionStatus.STOPPED)
        print(f"[run_analysis] stop session={session_id}")


@router.post("/start", response_model=VideoResponse)
async def start_analysis(request: VideoRequest, background_tasks: BackgroundTasks):
    """启动视频流分析

    Args:
        request: 分析请求
        background_tasks: 后台任务

    Returns:
        会话信息
    """
    session_id = str(uuid.uuid4())

    # 验证流地址 (简单验证)
    if not request.stream_url.startswith('rtsp://'):
        raise HTTPException(
            status_code=400,
            detail="Invalid stream URL. Must start with rtsp://"
        )

    # 初始化会话信息
    connection_manager.ensure_session(session_id, request.stream_url)
    connection_manager.update_session_stream(session_id, request.stream_url)
    connection_manager.update_session_status(session_id, SessionStatus.PENDING)

    # 启动后台分析任务
    task = asyncio.create_task(
        run_analysis(session_id, request.stream_url)
    )
    _analysis_tasks[session_id] = task

    return VideoResponse(
        session_id=session_id,
        status="running",
        message="Analysis started successfully"
    )


@router.post("/stop")
async def stop_analysis(request: VideoStopRequest):
    """停止视频流分析

    Args:
        request: 停止请求

    Returns:
        停止结果
    """
    session_id = request.session_id

    if session_id in _analysis_tasks:
        task = _analysis_tasks[session_id]
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        del _analysis_tasks[session_id]

    connection_manager.update_session_status(session_id, SessionStatus.STOPPED)

    return {
        "session_id": session_id,
        "status": "stopped",
        "message": "Analysis stopped"
    }


@router.get("/sessions", response_model=list)
async def list_sessions():
    """列出所有活跃会话

    Returns:
        会话列表
    """
    return connection_manager.get_active_sessions()


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """获取会话详情

    Args:
        session_id: 会话 ID

    Returns:
        会话信息
    """
    session = connection_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionInfo(
        session_id=session.session_id,
        status=session.status.value,
        frame_count=session.frame_count,
        stream_url=session.stream_url
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查

    Returns:
        健康状态
    """
    import time
    import torch

    inferencer = get_inferencer()

    return HealthResponse(
        status="healthy",
        model_loaded=True,
        gpu_available=torch.cuda.is_available(),
        uptime_seconds=0  # TODO: 添加启动时间追踪
    )


# 简单的前端页面
frontend_router = APIRouter(tags=["frontend"])


@frontend_router.get("/")
async def index():
    """主页面"""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content=content)
