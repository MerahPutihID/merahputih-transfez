FROM python:3.9-slim

WORKDIR /app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8083

RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'if [ "$MODE" = "scheduler" ]; then' >> /entrypoint.sh && \
    echo '    python -m app.main scheduler' >> /entrypoint.sh && \
    echo 'else' >> /entrypoint.sh && \
    echo '    uvicorn app.main:app --host 0.0.0.0 --port $PORT' >> /entrypoint.sh && \
    echo 'fi' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

EXPOSE $PORT

ENTRYPOINT ["/entrypoint.sh"]