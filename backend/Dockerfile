FROM python:3.10-slim

LABEL org.opencontainers.image.authors="Serhii TK" \
      org.opencontainers.image.vendor="Serhii TK" \
      org.opencontainers.image.title="Hefner Sprach Hub Backend" \
      org.opencontainers.image.licenses="LicenseRef-Proprietary"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 1212

CMD ["bash", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn Studentlist.wsgi:application --bind 0.0.0.0:1212 --workers 3 --timeout 120"]
