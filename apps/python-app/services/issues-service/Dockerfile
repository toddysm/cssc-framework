# issues-service Dockerfile.
#
# Build context is apps/python-app/ (so the shared libs/cssc_common library is
# available):
#
#   docker build -f services/issues-service/Dockerfile -t issues-service .
FROM python:3.12-slim

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
USER appuser

EXPOSE 8080
CMD ["uvicorn", "issues_service.app:app", "--host", "0.0.0.0", "--port", "8080"]
