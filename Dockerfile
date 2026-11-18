# 两阶段：依赖层与代码层分开，改代码不会重装依赖（分层缓存）
FROM python:3.12-slim AS base
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && uv pip install --system -r pyproject.toml

COPY agent ./agent
COPY eval ./eval
EXPOSE 8000
# 模型在宿主机 Ollama 上，容器内用 host.docker.internal 访问
ENV OLLAMA_HOST=http://host.docker.internal:11434
CMD ["uvicorn", "agent.app:app", "--host", "0.0.0.0", "--port", "8000"]
