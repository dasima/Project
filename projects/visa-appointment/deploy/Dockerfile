FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements.txt \
    && groupadd --system visa \
    && useradd --system --gid visa --home-dir /app visa

COPY --chown=visa:visa backend /app/backend
RUN mkdir -p /app/var /app/backend/staticfiles \
    && chown visa:visa /app/var /app/backend/staticfiles
WORKDIR /app/backend
USER visa

# Build-only settings: private .env and runtime credentials never enter the image.
RUN DJANGO_DEBUG=true DJANGO_SECRET_KEY=build-only-static-assets \
    python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-"]
