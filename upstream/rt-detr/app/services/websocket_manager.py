"""
WebSocket 连接管理模块
支持实时视频帧和告警推送
"""

import json
import base64
import time
import uuid
from typing import Dict, Set, Optional
from fastapi import WebSocket
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import cv2


class SessionStatus(Enum):
    """会话状态"""
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AnalysisSession:
    """分析会话"""
    session_id: str
    stream_url: str
    status: SessionStatus = SessionStatus.PENDING
    frame_count: int = 0
    start_time: Optional[float] = None
    websocket: Optional[WebSocket] = None


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # session_id -> {websocket connections}
        self._connections: Dict[str, Set[WebSocket]] = {}
        # session_id -> AnalysisSession
        self._sessions: Dict[str, AnalysisSession] = {}

    def ensure_session(self, session_id: str, stream_url: str = "") -> AnalysisSession:
        """
        确保会话存在，不存在则创建。

        Args:
            session_id: 会话 ID
            stream_url: 流地址（可选）

        Returns:
            AnalysisSession 对象
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = AnalysisSession(
                session_id=session_id,
                stream_url=stream_url,
                status=SessionStatus.PENDING
            )
        else:
            # 仅在尚未设置流地址时补充
            if stream_url and not self._sessions[session_id].stream_url:
                self._sessions[session_id].stream_url = stream_url
        return self._sessions[session_id]

    async def connect(self, session_id: str, websocket: WebSocket) -> AnalysisSession:
        """建立 WebSocket 连接并创建会话

        Args:
            session_id: 会话 ID
            websocket: WebSocket 连接

        Returns:
            AnalysisSession 对象
        """
        await websocket.accept()

        session = self.ensure_session(session_id)

        if session_id not in self._connections:
            self._connections[session_id] = set()

        self._connections[session_id].add(websocket)

        return session

    def disconnect(self, session_id: str, websocket: WebSocket):
        """断开 WebSocket 连接"""
        if session_id in self._connections:
            self._connections[session_id].discard(websocket)
            if not self._connections[session_id]:
                del self._connections[session_id]

        if session_id in self._sessions:
            self._sessions[session_id].status = SessionStatus.STOPPED

    def get_session(self, session_id: str) -> Optional[AnalysisSession]:
        """获取会话信息"""
        return self._sessions.get(session_id)

    def update_session_stream(self, session_id: str, stream_url: str):
        """更新会话流地址"""
        session = self.ensure_session(session_id, stream_url)
        session.stream_url = stream_url

    def update_session_status(self, session_id: str, status: SessionStatus | str):
        """更新会话状态"""
        session = self.ensure_session(session_id)
        if isinstance(status, str):
            try:
                status = SessionStatus(status)
            except ValueError:
                status = SessionStatus.ERROR
        session.status = status

    def increment_frame_count(self, session_id: str):
        """增加帧计数"""
        session = self.ensure_session(session_id)
        session.frame_count += 1

    async def send_json(self, session_id: str, data: dict):
        """向指定会话的所有连接发送 JSON 数据"""
        # 确保会话存在，避免后续统计访问异常
        self.ensure_session(session_id)
        if session_id in self._connections:
            message = json.dumps(data)
            for connection in self._connections[session_id]:
                try:
                    await connection.send_text(message)
                except Exception:
                    # 连接断开时移除
                    self._connections[session_id].discard(connection)

    async def send_frame_result(
        self,
        session_id: str,
        base64_frame: str,
        detections: list,
        timestamp: float,
        frame_index: int
    ):
        """发送帧分析结果

        Args:
            session_id: 会话 ID
            base64_frame: Base64 编码的 JPEG 图像
            detections: 检测结果列表
            timestamp: 时间戳
            frame_index: 帧序号
        """
        result = {
            "type": "frame_result",
            "session_id": session_id,
            "timestamp": timestamp,
            "frame_index": frame_index,
            "annotated_frame": base64_frame,
            "detections": detections
        }
        await self.send_json(session_id, result)
        self.increment_frame_count(session_id)

    async def send_alert(
        self,
        session_id: str,
        detection: dict,
        confidence_threshold: float = 0.5
    ):
        """发送告警消息

        Args:
            session_id: 会话 ID
            detection: 检测结果
            confidence_threshold: 告警置信度阈值
        """
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
        await self.send_json(session_id, alert)

    async def send_error(self, session_id: str, error_message: str):
        """发送错误消息"""
        error = {
            "type": "error",
            "session_id": session_id,
            "timestamp": time.time(),
            "message": error_message
        }
        await self.send_json(session_id, error)

    async def send_status(self, session_id: str, status: str, message: str = ""):
        """发送状态消息"""
        status_data = {
            "type": "status",
            "session_id": session_id,
            "timestamp": time.time(),
            "status": status,
            "message": message
        }
        await self.send_json(session_id, status_data)

    def get_active_sessions(self) -> list:
        """获取所有活跃会话"""
        return [
            {
                "session_id": sid,
                "status": sess.status.value if isinstance(sess.status, SessionStatus) else str(sess.status),
                "frame_count": sess.frame_count,
                "stream_url": sess.stream_url
            }
            for sid, sess in self._sessions.items()
        ]


class FrameEncoder:
    """帧编码器"""

    @staticmethod
    def encode_jpeg(frame, quality: int = 70) -> str:
        """将 OpenCV 帧编码为 Base64 JPEG

        Args:
            frame: OpenCV BGR 图像
            quality: JPEG 质量 (1-100)

        Returns:
            Base64 编码的 JPEG 字符串
        """
        _, buffer = cv2.imencode(
            '.jpg',
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, quality]
        )
        return base64.b64encode(buffer).decode('utf-8')

    @staticmethod
    def resize(frame, max_width: int = 800) -> np.ndarray:
        """调整帧大小

        Args:
            frame: OpenCV 图像
            max_width: 最大宽度

        Returns:
            调整后的图像
        """
        height, width = frame.shape[:2]
        if width > max_width:
            ratio = max_width / width
            new_width = max_width
            new_height = int(height * ratio)
            return cv2.resize(frame, (new_width, new_height))
        return frame


# 导出单例实例
connection_manager = ConnectionManager()
frame_encoder = FrameEncoder()
