#!/bin/bash
# Wait for E2E services to be healthy

set -e

TIMEOUT=120
ELAPSED=0
SERVICES=("agentfield:8080" "mock-middleman:8091" "mock-github:8092" "mock-gitlab:8093")

echo "Waiting for services to be healthy (timeout: ${TIMEOUT}s)..."

while [ $ELAPSED -lt $TIMEOUT ]; do
    ALL_HEALTHY=true

    for SERVICE in "${SERVICES[@]}"; do
        NAME="${SERVICE%%:*}"
        PORT="${SERVICE##*:}"

        # AgentField doesn't have /health, check root instead
        if [ "$NAME" = "agentfield" ]; then
            URL="http://localhost:${PORT}/"
        else
            URL="http://localhost:${PORT}/health"
        fi

        if ! curl -sf "$URL" > /dev/null 2>&1; then
            ALL_HEALTHY=false
            echo "  ⏳ Waiting for ${NAME} at ${URL}..."
            break
        fi
    done

    if [ "$ALL_HEALTHY" = true ]; then
        echo "✅ All services are healthy!"
        exit 0
    fi

    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

echo "❌ Timeout waiting for services to become healthy"
echo ""
echo "Service status:"
for SERVICE in "${SERVICES[@]}"; do
    NAME="${SERVICE%%:*}"
    PORT="${SERVICE##*:}"

    # AgentField doesn't have /health, check root instead
    if [ "$NAME" = "agentfield" ]; then
        URL="http://localhost:${PORT}/"
    else
        URL="http://localhost:${PORT}/health"
    fi

    if curl -sf "$URL" > /dev/null 2>&1; then
        echo "  ✅ ${NAME}: healthy"
    else
        echo "  ❌ ${NAME}: not responding"
    fi
done

exit 1
