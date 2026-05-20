# ============================================================
# Agent Hub · Dockerfile
# 多阶段构建：第一阶段安装 Python 依赖，第二阶段运行
# ============================================================

# ---- 第一阶段：依赖安装 ----
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- 第二阶段：运行 ----
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制 Python 依赖
COPY --from=builder /root/.local /root/.local

# 确保依赖在 PATH 中
ENV PATH=/root/.local/bin:$PATH

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data

EXPOSE 8000

# 使用 exec 形式保证信号正确处理
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
