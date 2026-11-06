FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY requirements-deploy.txt ./
RUN pip install --no-cache-dir --disable-pip-version-check \
    -r requirements-deploy.txt

COPY --chown=app:app fuqianhecha ./fuqianhecha
COPY --chown=app:app knowledge ./knowledge
COPY --chown=app:app web ./web

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"]

CMD ["gunicorn", "--bind=0.0.0.0:8000", "--workers=2", "--threads=4", "--worker-class=gthread", "--worker-tmp-dir=/tmp", "--no-control-socket", "--timeout=30", "--graceful-timeout=30", "--max-requests=1000", "--max-requests-jitter=100", "--access-logfile=-", "--error-logfile=-", "fuqianhecha.web:application"]
