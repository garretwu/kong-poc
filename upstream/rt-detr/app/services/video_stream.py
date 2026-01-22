"""
视频流拉取模块
仅支持 RTSP 协议
"""

import asyncio
import cv2
import time
from typing import AsyncIterator, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor


@dataclass
class VideoFrame:
    """视频帧数据结构"""
    frame: any                    # OpenCV frame (BGR 格式)
    timestamp: float             # 帧时间戳 (Unix timestamp)
    frame_index: int             # 帧序号
    width: int                   # 帧宽度
    height: int                  # 帧高度


class VideoStreamError(Exception):
    """视频流错误"""
    pass


class RTSPStreamReader:
    """RTSP 视频流拉取器"""

    def __init__(self, stream_url: str, use_ffmpeg: bool = False):
        self.stream_url = stream_url
        self.use_ffmpeg = use_ffmpeg
        self.cap = None
        self.running = False
        self.frame_index = 0
        self.executor = ThreadPoolExecutor(max_workers=1)

    def connect(self) -> bool:
        """连接 RTSP 流"""
        try:
            # 优先使用 TCP 以避免 UDP 丢包导致的随机中断
            self.cap = cv2.VideoCapture(self.stream_url, cv2.CAP_FFMPEG)
            return self.cap.isOpened()
        except Exception:
            return False

    def get_stream_info(self) -> Optional[dict]:
        """获取流基础信息"""
        if self.cap is None or not self.cap.isOpened():
            return None
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(self.cap.get(cv2.CAP_PROP_FPS)) or 0.0
        return {
            "width": width,
            "height": height,
            "fps": fps
        }

    async def read_frame(self) -> Optional[VideoFrame]:
        """异步读取一帧"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._read_frame_sync
        )

    def _read_frame_sync(self) -> Optional[VideoFrame]:
        if self.cap is None:
            return None

        ret, frame = self.cap.read()
        if not ret:
            return None

        height, width = frame.shape[:2]
        self.frame_index += 1

        return VideoFrame(
            frame=frame,
            timestamp=time.time(),
            frame_index=self.frame_index,
            width=width,
            height=height
        )

    async def stream_frames(self, max_frames: Optional[int] = None) -> AsyncIterator[VideoFrame]:
        """异步迭代视频帧"""
        self.running = True
        frame_count = 0

        while self.running:
            if max_frames is not None and frame_count >= max_frames:
                break

            frame = await self.read_frame()
            if frame is None:
                break

            frame_count += 1
            yield frame
            await asyncio.sleep(0)

    def stop(self):
        """停止拉流"""
        self.running = False
        if self.cap is not None:
            self.cap.release()


def create_stream_reader(stream_url: str) -> RTSPStreamReader:
    """创建视频流读取器

    Args:
        stream_url: 流地址 (RTSP)

    Returns:
        对应的 StreamReader 实例
    """
    if stream_url.startswith('rtsp://'):
        return RTSPStreamReader(stream_url)
    raise VideoStreamError("Only RTSP stream URLs are supported")
