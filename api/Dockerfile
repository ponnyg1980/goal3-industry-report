# Report engine API for Cloud Run. The engine modules sit in the parent
# directory, so we copy the whole app and run uvicorn from the repo root.
FROM python:3.12-slim
WORKDIR /app
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt
COPY . /app
ENV PORT=8080
# Cloud Run sets $PORT; bind to it.
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
