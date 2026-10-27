FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app --no-create-home app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app app.py index.html login.html ./

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/', timeout=3)"]

CMD ["gunicorn", "--bind=0.0.0.0:8000", "--workers=2", "--threads=4", "--access-logfile=-", "--error-logfile=-", "--timeout=30", "app:app"]
