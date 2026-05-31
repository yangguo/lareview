FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_URL=http://127.0.0.1:8000

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN mkdir -p public && npm run build

FROM node:20-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV NEXT_TELEMETRY_DISABLED=1
ENV BACKEND_PORT=8000
ENV PORT=7860
ENV NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
    && python3 -m venv "$VIRTUAL_ENV" \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY src/ ./src/
COPY config/ ./config/
COPY --from=frontend-builder /app/frontend/.next/standalone ./frontend/
COPY --from=frontend-builder /app/frontend/.next/static ./frontend/.next/static
COPY --from=frontend-builder /app/frontend/public ./frontend/public
COPY scripts/start-space.sh ./scripts/start-space.sh

RUN chmod +x ./scripts/start-space.sh \
    && mkdir -p /tmp/lareview_runs logs assets/uploads

EXPOSE 7860

CMD ["./scripts/start-space.sh"]
