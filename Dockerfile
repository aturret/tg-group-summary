FROM python:3.13-slim

RUN pip install --no-cache-dir uv

LABEL authors="ATurret"
WORKDIR /app

# 2. 安装系统依赖 (保持不变)
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. 配置 uv 环境变量
# UV_COMPILE_BYTECODE=1: 编译 pyc 文件，加快容器启动速度
# UV_LINK_MODE=copy: 防止在某些 Docker 存储驱动中硬链接失败
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# 4. 复制依赖文件 (使用 uv.lock 而不是 requirements.txt)
# 只要这两个文件不变，Docker 缓存就会被命中
COPY pyproject.toml uv.lock ./

# 5. 安装依赖
# --frozen: 严格按照 lock 文件安装，不更新版本
# --no-dev: 不安装开发依赖 (如 pytest 等)
# --mount: 使用缓存挂载，加快重复构建速度
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# 6. 将 uv 创建的虚拟环境加入 PATH
# 这一步至关重要，它让后续的 `python` 命令直接使用虚拟环境中的解释器
ENV PATH="/app/.venv/bin:$PATH"

# 7. 复制源代码
COPY app/ ./app/

# 8. 环境变量设置 (保持你的逻辑)
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 9. 权限处理 (保持不变，但要确保用户拥有 .venv 的权限)
RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app
USER app

# 10. 启动命令
# 由于 PATH 已设置，这里的 python 会自动使用 /app/.venv/bin/python
CMD ["python", "app/main.py"]