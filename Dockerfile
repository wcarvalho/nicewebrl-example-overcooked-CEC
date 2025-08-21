FROM python:3.10-slim

RUN apt update && apt install -y curl procps git cmake build-essential

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy everything
COPY . /app

# Install dependencies with uv
RUN uv sync --frozen

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=DEBUG

CMD ["uv", "run", "python", "web_app.py", "counter_circuit"]