FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖 (OpenCV 需要) - Updated for Debian trixie
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/

# 创建模型目录
RUN mkdir -p /models

# 暴露端口
EXPOSE 8080

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV RT_DETR_MODEL_PATH=/models/rt-detr.pt
ENV RT_DETR_DEVICE=cuda

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
