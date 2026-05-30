#!/bin/bash
# Initialize kata projects for E2E testing

set -e

# Wait for kata daemon to be ready
echo "Waiting for kata daemon..."
sleep 3

# Create workspace directories with git repos
mkdir -p /kata-home/test-repo
cd /kata-home/test-repo
if [ ! -d ".git" ]; then
    git init
    git config user.email "test@e2e.local"
    git config user.name "E2E Test"
    echo "# Test Repo" > README.md
    git add README.md
    git commit -m "Initial commit"
fi

# Initialize kata in test-repo
if ! kata list 2>/dev/null; then
    echo "Initializing kata project: test-repo"
    kata init
fi

# Create test-infra workspace
mkdir -p /kata-home/test-infra
cd /kata-home/test-infra
if [ ! -d ".git" ]; then
    git init
    git config user.email "test@e2e.local"
    git config user.name "E2E Test"
    echo "# Test Infra" > README.md
    git add README.md
    git commit -m "Initial commit"
fi

# Initialize kata in test-infra
if ! kata list 2>/dev/null; then
    echo "Initializing kata project: test-infra"
    kata init
fi

echo "Kata projects initialized successfully"
