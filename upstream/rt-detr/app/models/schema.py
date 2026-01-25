"""
Pydantic 数据模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class VideoRequest(BaseModel):
    """视频流分析请求"""
    stream_url: str = Field(
        ...,
        description="视频流地址 (RTSP)",
        json_schema_extra={"example": "rtsp://mediamtx:8554/camera"}
    )
    enable_drawing: bool = Field(
        default=True,
        description="是否返回标注后的帧"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API Key (由 Kong 注入)"
    )


class VideoResponse(BaseModel):
    """视频流分析响应"""
    session_id: str
    status: str = Field(..., description="会话状态")
    message: str


class VideoStopRequest(BaseModel):
    """停止分析请求"""
    session_id: str


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    status: str
    frame_count: int
    stream_url: str
    start_time: Optional[datetime] = None


class DetectionResult(BaseModel):
    """单个检测结果"""
    class_id: int
    class_name: str
    bbox: List[float] = Field(..., description="边界框 [x1, y1, x2, y2]")
    confidence: float


class FrameResult(BaseModel):
    """帧分析结果"""
    type: str = "frame_result"
    session_id: str
    timestamp: float
    frame_index: int
    detections: List[DetectionResult]
    annotated_frame: Optional[str] = None


class AlertMessage(BaseModel):
    """告警消息"""
    type: str = "alert"
    session_id: str
    timestamp: float
    data: DetectionResult


class ErrorMessage(BaseModel):
    """错误消息"""
    type: str = "error"
    session_id: str
    timestamp: float
    message: str


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    model_loaded: bool
    gpu_available: bool
    uptime_seconds: float
