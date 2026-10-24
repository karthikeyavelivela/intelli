FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
RUN useradd -m -u 1000 app && mkdir -p /data/datasets && chown -R app /data /app
COPY --chown=app docker/backend-entrypoint.sh /entrypoint.sh
USER app
ENV DATA_DIR=/data/datasets
EXPOSE 8000
ENTRYPOINT ["bash", "/entrypoint.sh"]
CMD ["api"]
