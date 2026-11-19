FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 YOLO_CONFIG_DIR=/tmp/ultralytics
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 routex && useradd --uid 10001 --gid routex --create-home routex
RUN python -m pip install --upgrade pip==26.2.0 \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.0 torchvision==0.29.0
COPY backend/requirements.runtime.txt /tmp/requirements.txt
RUN python -m pip install -r /tmp/requirements.txt
COPY backend /app/backend
COPY vision /app/vision
COPY ml /app/ml
COPY deploy /app/deploy
RUN python deploy/prepare_assets.py && mkdir -p /app/data/uploads /app/data/videos \
    && mkdir -p /tmp/ultralytics && chown -R routex:routex /app/data /app/yolo11n.pt /tmp/ultralytics
USER 10001:10001
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health/ready', timeout=3)"
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]

FROM runtime AS test
USER root
RUN python -m pip install pytest==9.1.1 pip-audit==2.10.0
COPY tests /app/tests
COPY pytest.ini /app/pytest.ini
RUN chown -R routex:routex /app
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "--disable-warnings"]
