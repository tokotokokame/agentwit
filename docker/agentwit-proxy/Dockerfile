FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install agentwit
RUN pip install --no-cache-dir agentwit

# Create log directory
RUN mkdir -p /logs

EXPOSE 8080

# TARGET_URL and WEBHOOK_URL are provided via environment variables at runtime.
# The proxy writes JSONL audit logs to /logs/audit.jsonl.
CMD ["sh", "-c", \
     "agentwit proxy http \
       --target \"${TARGET_URL}\" \
       --host 0.0.0.0 \
       --port 8080 \
       --log-dir /logs \
       ${WEBHOOK_URL:+--webhook \"${WEBHOOK_URL}\"}"]
