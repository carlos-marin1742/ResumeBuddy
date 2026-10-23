# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20.20.2-slim AS frontend-build

WORKDIR /app/client
COPY client/package*.json ./
RUN npm ci
COPY client/ ./
RUN npm run build

# ── Stage 2: Python backend + Playwright ─────────────────────────────────────
FROM python:3.11.17-slim-trixie

# System deps required by Playwright/Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers in a shared path the non-root user can read
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw
RUN playwright install chromium && chmod -R a+rX /opt/pw

# Copy backend source
COPY backend/ .

# Copy built frontend into backend's static directory
COPY --from=frontend-build /app/client/dist ./static

# Ensure outputs directory exists
RUN mkdir -p outputs && useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app

USER appuser

# The app listens on $PORT (hosting platforms set it) and defaults to 8000.
EXPOSE 8000

# Liveness only (/health). The forwarded-proto header satisfies REQUIRE_HTTPS.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request as u; u.urlopen(u.Request('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), headers={'X-Forwarded-Proto': 'https'}), timeout=4)"]

# Keep this at one uvicorn worker: RESUME_STORE and the rate-limit counters live
# in process memory, so extra workers would each hold their own copy and
# per-IP/per-user limits and in-flight resume sessions would stop being shared.
# FORWARDED_ALLOW_IPS names the proxy addresses whose X-Forwarded-* headers are
# trusted; the default trusts only loopback, so set it for the platform's proxy.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=${FORWARDED_ALLOW_IPS:-127.0.0.1}"]
