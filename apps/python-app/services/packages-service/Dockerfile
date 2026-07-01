# packages-service Dockerfile.
#
# Build context is apps/python-app/ (so the shared libs/cssc_common library is
# available):
#
#   docker build -f services/packages-service/Dockerfile -t packages-service .
# Base image is sourced from the package repo (golden). Overridable for local
# dev before golden/python:3.12-slim has been promoted.
ARG BASE_IMAGE=ghcr.io/toddysm/golden/python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install the shared library first so its layer is cached across services.
COPY libs/cssc_common /tmp/cssc_common
RUN pip install --no-cache-dir /tmp/cssc_common && rm -rf /tmp/cssc_common

COPY services/packages-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/packages-service/src ./src

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser
USER 10001

EXPOSE 8080
CMD ["uvicorn", "packages_service.app:app", "--host", "0.0.0.0", "--port", "8080"]
