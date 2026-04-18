FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY subnet-vla/video-robot-eval /app/video-robot-eval
COPY services/vla-video-analyzer/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/vla-video-analyzer/main_api.py /app/main_api.py

ENV PYTHONPATH=/app/video-robot-eval
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "main_api:app", "--host", "0.0.0.0", "--port", "8000"]
