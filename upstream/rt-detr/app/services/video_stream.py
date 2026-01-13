"""
视频流拉取模块
支持 FLV/HTTP/RTSP 协议
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


class FLVStreamReader:
    """FLV/HTTP 视频流拉取器"""

    def __init__(self, stream_url: str):
        self.stream_url = stream_url
        self.cap = None
        self.running = False
        self.frame_index = 0
        self.executor = ThreadPoolExecutor(max_workers=1)

    def connect(self) -> bool:
        """连接视频流

        Returns:
            连接是否成功
        """
        try:
            self.cap = cv2.VideoCapture(self.stream_url)
            if not self.cap.isOpened():
                raise VideoStreamError(f"Failed to open stream: {self.stream_url}")
            return True
        except Exception as e:
            raise VideoStreamError(f"Connection error: {str(e)}")

    def _read_frame_sync(self) -> Optional[VideoFrame]:
        """同步读取一帧 (在线程池中执行)"""
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

    async def read_frame(self) -> Optional[VideoFrame]:
        """异步读取一帧

        Returns:
            VideoFrame 或 None (流结束)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._read_frame_sync)

    async def stream_frames(self, max_frames: Optional[int] = None) -> AsyncIterator[VideoFrame]:
        """异步迭代视频帧

        Args:
            max_frames: 最大帧数，None 表示无限

        Yields:
            VideoFrame 对象

        Raises:
            VideoStreamError: 流读取错误
        """
        self.running = True
        frame_count = 0

        try:
            while self.running:
                if max_frames is not None and frame_count >= max_frames:
                    break

                frame = await self.read_frame()
                if frame is None:
                    break

                frame_count += 1
                yield frame

                # 短暂让出控制权，避免占用全部 CPU
                await asyncio.sleep(0)
        except Exception as e:
            raise VideoStreamError(f"Stream read error: {str(e)}")

    def stop(self):
        """停止拉流，释放资源"""
        self.running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.cap is not None and self.cap.isOpened()

    def get_stream_info(self) -> Optional[dict]:
        """获取流信息

        Returns:
            流信息字典或 None
        """
        if self.cap is None:
            return None

        return {
            "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": self.cap.get(cv2.CAP_PROP_FPS),
            "codec": int(self.cap.get(cv2.CAP_PROP_FOURCC))
        }


class RTSPStreamReader:
    """RTSP 视频流拉取器 (需要 MediaMTX 转换时使用)

    注意：建议使用 MediaMTX 将 RTSP 转换为 FLV，
    直接读取 RTSP 需要安装 ffmpeg 依赖
    """

    def __init__(self, stream_url: str, use_ffmpeg: bool = False):
        self.stream_url = stream_url
        self.use_ffmpeg = use_ffmpeg
        self.cap = None
        self.running = False
        self.frame_index = 0
        self.executor = ThreadPoolExecutor(max_workers=1)

    def connect(self) -> bool:
        """连接 RTSP 流"""
        # 优先使用 MediaMTX 转换后的 FLV 流
        # 直接 RTSP 需要更多依赖
        try:
            self.cap = cv2.VideoCapture(self.stream_url)
            return self.cap.isOpened()
        except Exception:
            return False

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


def create_stream_reader(stream_url: str) -> FLVStreamReader:
    """创建视频流读取器

    Args:
        stream_url: 流地址 (HTTP/FLV/RTSP)

    Returns:
        对应的 StreamReader 实例
    """
    if stream_url.startswith('rtsp://'):
        return RTSPStreamReader(stream_url)
    else:
        # HTTP/FLV 默认使用 FLV 读取器
        return FLVStreamReader(stream_url)
