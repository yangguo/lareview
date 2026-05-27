FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY src/ ./src/
COPY config/ ./config/

RUN mkdir -p /tmp/lareview_runs logs

EXPOSE 8000

CMD ["python", "-m", "src.main", "-m", "http", "-p", "8000"]
