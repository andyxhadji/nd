# ND Scripts

Helper scripts for local development and testing.

## Approval Tool

Manually approve paused AgentField executions during development.

### Usage

```bash
# Approve with default "approved" decision
./scripts/approve.py <approval_request_id>

# Approve with custom decision
./scripts/approve.py <approval_request_id> approved "Looks good!"

# Reject
./scripts/approve.py <approval_request_id> rejected "Please fix the bug"

# Request changes
./scripts/approve.py <approval_request_id> request_changes "Add tests"
```

### Finding Approval Request IDs

1. Check the AgentField UI at http://localhost:8081/ui/runs/
2. Look at worker logs:
   ```bash
   docker compose logs worker-1 worker-2 | grep approval_request_id
   ```
3. Use the helper script:
   ```bash
   ./scripts/list-approvals.sh
   ```

### How It Works

The worker calls `app.pause(approval_request_id=...)` which puts the execution in a `waiting` state. To resume:

1. The external approval system (or this script) sends a webhook to AgentField
2. The webhook includes the `requestId`, `decision`, and optional `feedback`
3. AgentField verifies the HMAC-SHA256 signature (using `AGENTFIELD_APPROVAL_WEBHOOK_SECRET`)
4. AgentField resumes the execution with the approval result

### Configuration

The webhook secret is configured in `docker-compose.yml`:

```yaml
agentfield:
  environment:
    - AGENTFIELD_APPROVAL_WEBHOOK_SECRET=nd-approval-secret-dev
```

The approval script uses the same secret to sign webhooks.

### Production Usage

In production, integrate with a proper approval system:
- Slack bot with approve/reject buttons
- Web dashboard for reviewing pending tasks
- GitHub comment triggers
- Email-based approval links

The approval system should POST to `/api/v1/webhooks/approval-response` with proper HMAC signing.
