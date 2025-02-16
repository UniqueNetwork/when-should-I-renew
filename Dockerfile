FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

COPY app.py .

CMD ["/app/app.py", "--host", "0.0.0.0", "--port", "43987", "--task", "2095"]