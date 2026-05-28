#!/usr/bin/env python3
"""Simple approval tool for AgentField paused executions.

Usage:
    ./scripts/approve.py <approval_request_id> [decision] [feedback]

Examples:
    ./scripts/approve.py post-537b approved "Looks good"
    ./scripts/approve.py post-537b rejected "Try again"
    ./scripts/approve.py post-537b request_changes "Fix the typo first"

Decision options: approved, rejected, request_changes
Default: approved
"""

import hashlib
import hmac
import json
import sys
import urllib.error
import urllib.request
from typing import Literal

Decision = Literal["approved", "rejected", "request_changes"]

AGENTFIELD_URL = "http://localhost:8081"
WEBHOOK_SECRET = "nd-approval-secret-dev"


def approve_request(
    request_id: str,
    decision: Decision = "approved",
    feedback: str = "",
) -> dict:
    """Send approval webhook to AgentField with HMAC signature."""
    url = f"{AGENTFIELD_URL}/api/v1/webhooks/approval-response"

    payload = {
        "requestId": request_id,
        "decision": decision,
    }

    if feedback:
        payload["feedback"] = feedback

    data = json.dumps(payload).encode("utf-8")

    # Generate HMAC-SHA256 signature
    signature = hmac.new(WEBHOOK_SECRET.encode("utf-8"), data, hashlib.sha256).hexdigest()

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"HTTP {e.code} Error: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    request_id = sys.argv[1]
    decision = sys.argv[2] if len(sys.argv) > 2 else "approved"
    feedback = sys.argv[3] if len(sys.argv) > 3 else ""

    if decision not in ("approved", "rejected", "request_changes"):
        print(f"Invalid decision: {decision}")
        print("Valid options: approved, rejected, request_changes")
        sys.exit(1)

    print(f"Sending {decision} for approval request: {request_id}")
    if feedback:
        print(f"Feedback: {feedback}")

    result = approve_request(request_id, decision, feedback)

    print("\nResponse:")
    print(json.dumps(result, indent=2))
    print("\n✓ Approval sent successfully")


if __name__ == "__main__":
    main()
