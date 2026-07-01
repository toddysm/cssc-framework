# issues-service Dockerfile.
#
# Build context is apps/python-app/ (so the shared libs/cssc_common library is
# available):
#
#   docker build -f services/issues-service/Dockerfile -t issues-service .
# Base image is sourced from the package repo (golden). Overridable for local
# dev if the golden tag is not yet available.
ARG BASE_IMAGE=ghcr.io/toddysm/golden/python:3.14-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY libs/cssc_common /tmp/cssc_common
RUN pip install --no-cache-dir /tmp/cssc_common && rm -rf /tmp/cssc_common

COPY services/issues-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/issues-service/src ./src

RUN useradd --create-home --uid 10001 appuser
USER 10001

EXPOSE 8080
CMD ["uvicorn", "issues_service.app:app", "--host", "0.0.0.0", "--port", "8080"]
