FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 TMPDIR=/scratch
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 viewtube && useradd -u 10001 -g viewtube -m viewtube \
    && mkdir /scratch && chown viewtube:viewtube /scratch
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY --chown=10001:10001 . .
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
