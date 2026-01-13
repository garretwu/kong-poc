"""
配置管理模块
"""

import os
from typing import Optional
from pydantic import BaseModel


class Settings(BaseModel):
    """应用配置"""
    # 模型配置
    model_path: str = "/models/rt-detr.pt"
    device: str = "cuda"
    confidence_threshold: float = 0.5

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False

    # 视频流配置
    stream_timeout: int = 30
    frame_quality: int = 70
    max_frame_width: int = 800

    # 告警配置
    alert_enabled: bool = True
    alert_confidence_threshold: float = 0.7

    # Kong 配置 (用于验证 API Key)
    kong_api_url: Optional[str] = None

    class Config:
        env_prefix = "RT_DETR_"


def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 默认配置实例
settings = get_settings()
