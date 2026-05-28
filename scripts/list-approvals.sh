#!/bin/bash
# List pending approval requests from worker logs

echo "=== Pending Approval Requests ==="
echo

docker compose logs worker-1 worker-2 2>/dev/null | \
  grep -E "approval_request_id|Pausing execution|pause_cascade" | \
  tail -20

echo
echo "To approve a request, run:"
echo "  ./scripts/approve.py <approval_request_id> approved \"Your feedback\""
