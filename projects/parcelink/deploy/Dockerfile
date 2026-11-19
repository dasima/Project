# Build the application and public edge as separate targets from one context.
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app/backend
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt 'gunicorn>=23,<24' \
    && groupadd --gid 10001 parcelink \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin parcelink
COPY --chown=10001:10001 backend/ /app/backend/
# A fresh named volume inherits this ownership. collectstatic runs as UID 10001.
RUN mkdir -p /app/backend/staticfiles \
    && touch /app/backend/staticfiles/.volume-init \
    && chown -R 10001:10001 /app/backend/staticfiles
USER 10001:10001
EXPOSE 8000
# Run migrations once as a release operation; never in each web process startup.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "--worker-tmp-dir", "/tmp"]

FROM caddy:2-alpine AS edge
COPY deploy/Caddyfile /etc/caddy/Caddyfile
# Explicit public allowlist: no backend, environment, repository, docs, or DB files.
COPY index.html app.js api.js data.js shipment-view.js site-config.js map.js styles.css map.css /srv/frontend/
EXPOSE 80 443 8080
