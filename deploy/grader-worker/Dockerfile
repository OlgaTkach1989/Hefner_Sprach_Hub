FROM python:3.12-slim

LABEL org.opencontainers.image.authors="Serhii TK" \
      org.opencontainers.image.vendor="Serhii TK" \
      org.opencontainers.image.title="Hefner Sprach Hub Grader Worker" \
      org.opencontainers.image.licenses="LicenseRef-Proprietary"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir nbgrader==0.9.5

COPY backend /app

CMD ["python", "manage.py", "process_training_grader_jobs", "--loop", "--sleep-seconds", "15"]
