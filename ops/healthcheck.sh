#!/bin/sh
set -e

# Query health endpoint
HEALTH_URL="http://localhost:${PORT:-8000}/health"
RESPONSE=$(wget -qO- "$HEALTH_URL" || curl -sf "$HEALTH_URL")

# Check if response is non-empty
if [ -z "$RESPONSE" ]; then
  echo "Empty response or health check failed"
  exit 1
fi

# Validate JSON content has "status": "ok"
if echo "$RESPONSE" | grep -q '"status":[[:space:]]*"ok"'; then
  exit 0
else
  echo "Unhealthy response: $RESPONSE"
  exit 1
fi
