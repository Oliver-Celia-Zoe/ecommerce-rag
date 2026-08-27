# ==========================================
# 生产环境 Dockerfile（多阶段构建）
# 构建：docker build -t air-fryer-backend:prod -f backend/Dockerfile backend/
# ==========================================
# 多阶段构建是企业级镜像的最佳实践：
#   - builder 阶段：装依赖（包含 uv、编译工具等，体积大）
#   - runtime 阶段：只复制 .venv 和源码，镜像小、安全
# 最终镜像不包含 uv、编译器、缓存等构建垃圾。

# ---------- 阶段 1：构建阶段（只装依赖）----------
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装 uv（Python 包管理器，比 pip 快 10 倍以上）
RUN pip install --no-cache-dir uv

# 先只复制依赖描述文件（利用 Docker 缓存层）
# 这样只要依赖不变，后续构建直接用缓存，秒级完成
COPY pyproject.toml uv.lock ./

# pyproject.toml 声明了 readme = "README.md"，但生产构建不需要文档
# 创建空文件避免 uv sync 因缺 README 报错
RUN touch README.md

# 用 uv sync 安装依赖到 .venv
# --frozen: 严格按 uv.lock 装，不解析新依赖（保证可复现构建）
# --no-dev: 不装开发依赖（pytest、black、mypy 等）
# --no-install-project: 只装依赖，不装项目本身（源码还没复制进来）
RUN uv sync --frozen --no-dev --no-install-project

# ---------- 阶段 2：运行阶段（最终镜像）----------
FROM python:3.12-slim AS runtime

WORKDIR /app

# 从 builder 复制装好的 .venv（含所有依赖）
COPY --from=builder /app/.venv /app/.venv

# 环境变量
# PATH 加入 .venv/bin：让 uvicorn、alembic 等命令直接可用
# PYTHONDONTWRITEBYTECODE=1：不生成 .pyc（省空间）
# PYTHONUNBUFFERED=1：日志实时输出（不缓冲）
# APP_ENV=production：标记生产环境（影响 LLM 选择等）
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

# 复制应用代码（只复制必要的）
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
# 知识文档目录（compose 会用 volume 覆盖，这里只是占位确保目录存在）
COPY data/ ./data/

EXPOSE 8000

# 启动命令：
# 1. alembic upgrade head —— 自动跑数据库迁移（建表/改表结构）
# 2. uvicorn —— 启动 FastAPI 应用
# 用 sh -c 串联：前一个成功才执行后一个
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
