#!/bin/bash
# Run E2E tests with docker-compose

set -e

# Change to repo root
cd "$(dirname "$0")/../../.."

echo "🚀 Starting E2E test environment..."
docker-compose -f tests/e2e/docker-compose.e2e.yml up -d

echo "⏳ Waiting for services to be ready..."
./tests/e2e/scripts/wait-for-services.sh

echo "🧪 Running E2E tests..."
pytest tests/e2e/ -v --tb=short "$@"

TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Tests failed. Collecting logs..."
    echo ""
    docker-compose -f tests/e2e/docker-compose.e2e.yml logs --tail=100 > e2e-test-logs.txt
    echo "Logs saved to e2e-test-logs.txt"
fi

echo ""
echo "🧹 Cleaning up..."
docker-compose -f tests/e2e/docker-compose.e2e.yml down -v

exit $TEST_EXIT_CODE
