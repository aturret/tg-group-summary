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

# 4. 复制依赖文件 (workspace root + all workspace members)
COPY pyproject.toml uv.lock ./
COPY packages/tg-summary-core/pyproject.toml ./packages/tg-summary-core/pyproject.toml
COPY apps/entrypoint/pyproject.toml ./apps/entrypoint/pyproject.toml

# 5. Create placeholder source dirs so uv sync can resolve workspace members
RUN mkdir -p packages/tg-summary-core/src/tg_summary_core && \
    touch packages/tg-summary-core/src/tg_summary_core/__init__.py

# 6. 安装依赖
# --frozen: 严格按照 lock 文件安装，不更新版本
# --no-dev: 不安装开发依赖 (如 pytest 等)
# --package: 同步 entrypoint app 的 runtime 依赖，包括 workspace 内的 tg-summary-core
# --mount: 使用缓存挂载，加快重复构建速度
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package tg-group-summary-entrypoint

# 7. 将 uv 创建的虚拟环境加入 PATH
ENV PATH="/app/.venv/bin:$PATH"

# 8. 复制源代码
COPY packages/tg-summary-core/src/ ./packages/tg-summary-core/src/
COPY apps/entrypoint/main.py ./apps/entrypoint/main.py
COPY conf/ ./conf/

# 9. 环境变量设置
ENV PYTHONUNBUFFERED=1
ENV PROMPT_YAML_PATH=/app/conf/prompt.yaml

# 10. 权限处理
RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app
USER app

# 11. 启动命令
CMD ["python", "apps/entrypoint/main.py"]
