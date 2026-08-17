# syntax=docker/dockerfile:1
# Multi-stage build: install deps in a builder, run as a non-root user.
FROM python:3.12-slim AS builder
WORKDIR /app
# The lock, not the ranges: an image built today must contain the versions that
# were tested, not whatever PyPI resolves at build time.
COPY requirements.lock .
RUN pip install --no-cache-dir --prefix=/install -r requirements.lock

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# Patch the base layer's OS packages. The base tag is rebuilt on the upstream image's
# schedule, not ours, so between rebuilds it carries whatever Debian security updates
# have landed since - and the CI Trivy gate blocks on exactly those: fixable HIGH/
# CRITICAL findings. Without this the image ships them and the gate fails on a CVE no
# code change here can address.
RUN apt-get update  && apt-get upgrade -y --no-install-recommends  && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/
COPY data/ ./data/
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
