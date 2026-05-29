#!/bin/bash
# Test against running agents in main docker-compose

set -e

# Change to repo root
cd "$(dirname "$0")/../../.."

echo "🧪 Testing running agents..."
echo ""
echo "Note: This assumes docker-compose is already running."
echo "If not, start it with: docker-compose up -d"
echo ""

# Check if services are running
if ! docker-compose ps | grep -q "Up"; then
    echo "⚠️  Warning: docker-compose services don't appear to be running."
    echo "Start them with: docker-compose up -d"
    exit 1
fi

echo "Running tests against live agents..."
pytest tests/e2e/ -v --use-running-agent "$@"

exit $?
