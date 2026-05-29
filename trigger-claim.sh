#!/bin/bash
# Trigger worker claim_task via AgentField API

RUN_ID=$(curl -s -X POST "http://localhost:8081/api/v1/agentic/invoke" \
  -H "Content-Type: application/json" \
  -d '{
    "invocation_target": "nd-worker:claim_task",
    "input_data": {"payload": ""}
  }' | jq -r '.run_id // empty')

if [ -n "$RUN_ID" ]; then
  echo "Triggered claim_task: $RUN_ID"
  echo "Monitor at: http://localhost:8081/ui/runs/$RUN_ID"
else
  echo "Failed to trigger claim_task"
  exit 1
fi
