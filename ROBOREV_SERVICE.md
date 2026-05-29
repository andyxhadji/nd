# Roborev Docker Service

## Overview

The `roborev` service runs as a separate container in the docker-compose stack, providing code review capabilities to the worker agents. This architecture allows roborev to access the same workspace directories as the workers while maintaining isolation.

## Architecture

```
┌─────────────────┐
│   worker-1      │──┐
│   worker-2      │  │ docker exec
└─────────────────┘  │
                     ▼
              ┌─────────────────┐
              │    roborev      │
              │                 │
              │  - workspace    │
              │  - .claude      │
              └─────────────────┘
```

When a worker needs to run roborev:
1. Worker detects it's in docker (checks for `/.dockerenv`)
2. Executes `docker exec -w <repo_path> hyper-furniture-roborev-1 roborev refine ...`
3. Roborev runs in its own container with access to the workspace

## Configuration

### docker-compose.yml

```yaml
roborev:
  build: .
  entrypoint: []
  command: ["tail", "-f", "/dev/null"]  # Keep container running
  volumes:
    - ${ND_WORKSPACE_ROOT:-./.nd-workspace}:/var/nd
    - ${HOME}/.claude:/root/.claude
    - ${HOME}/.claude.json:/root/.claude.json
  environment:
    - ANTHROPIC_MODEL=...
    - CLAUDE_CODE_USE_BEDROCK=1
    - AWS credentials...
  env_file:
    - .env.local
  restart: unless-stopped
```

### Worker Configuration

Workers need access to the docker socket to execute commands in other containers:

```yaml
worker-1:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock  # Required for docker exec
    - ${ND_WORKSPACE_ROOT:-./.nd-workspace}:/var/nd
    - ${HOME}/.claude:/root/.claude
```

### Dockerfile

The Dockerfile installs docker CLI to allow workers to execute docker commands:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*
```

## Worker Implementation

The worker's `run_roborev` reasoner detects the execution environment and routes accordingly:

```python
@app.reasoner()
async def run_roborev(
    repo_path: str,
    commit_sha: str,
    max_iterations: int = 3,
) -> dict:
    """Run roborev-refine for code quality validation via docker exec."""
    in_docker = os.path.exists("/.dockerenv")

    if in_docker:
        # Call roborev via docker exec to the roborev service
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-w", repo_path,
            "hyper-furniture-roborev-1",
            "roborev", "refine", "--max-iterations", str(max_iterations),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        # Running locally, call roborev directly
        proc = await asyncio.create_subprocess_exec(
            "roborev", "refine", "--max-iterations", str(max_iterations),
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
```

## Benefits

| Benefit | Description |
|---------|-------------|
| **Isolation** | Roborev runs in its own container, isolated from worker logic |
| **Shared workspace** | Both workers and roborev access the same `/var/nd` directory |
| **Agent access** | Roborev has access to Claude Code agent socket via `.claude` mount |
| **Horizontal scaling** | Multiple workers can call the same roborev service |
| **Resource control** | Roborev can have separate resource limits if needed |

## Agent Integration

### Claude Code CLI

The roborev container has Claude Code CLI (`@anthropic-ai/claude-code`) installed via npm. This provides:

- ✅ Standalone agent that works in containers
- ✅ Uses Bedrock API via AWS credentials from `.env.local`
- ✅ No dependency on host's Claude Code application
- ✅ Full automated code review and fix capabilities

The container installs:
- Node.js 22.x (required for Claude Code)
- `@anthropic-ai/claude-code` npm package (official Anthropic package)
- Symlink: `/usr/bin/claude` → Claude Code binary

### AWS Credentials

Roborev uses the same AWS credentials as the workers (from `.env.local`):
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `AWS_DEFAULT_REGION`

These credentials must have Bedrock InvokeModel permissions (use `mba-horizon` profile, not `assumed-horizon`).

### Container Naming

The worker hardcodes the container name `hyper-furniture-roborev-1`. If you rename the docker-compose project, update this in `nd/worker/agent.py`.

## Testing

### Verify Workspace Access

```bash
# Check roborev can see the workspace
docker exec hyper-furniture-roborev-1 ls -la /var/nd

# Check roborev has Claude Code socket (when CC is running)
docker exec hyper-furniture-roborev-1 test -S /root/.claude/sessions/claude-code.sock && echo "OK" || echo "NOT FOUND"
```

### Verify Worker Can Call Roborev

```bash
# Worker can execute docker commands
docker exec hyper-furniture-worker-1-1 docker ps

# Test roborev execution from worker
docker exec hyper-furniture-worker-1-1 docker exec -w /var/nd/work hyper-furniture-roborev-1 roborev --version
```

## Troubleshooting

### "permission denied while trying to connect to docker.sock"

The worker container needs access to the docker socket. Verify the volume mount:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

### "no agent available"

This error should not occur with the current setup since Claude Code CLI is installed. If you see this error:

1. Check that roborev container started successfully: `docker compose ps roborev`
2. Verify claude is installed: `docker exec hyper-furniture-roborev-1 which claude`
3. Test agent detection: `docker exec hyper-furniture-roborev-1 roborev check-agents`

If claude is not detected, rebuild the roborev container: `docker compose build roborev && docker compose up -d roborev`

### "container not found: hyper-furniture-roborev-1"

The roborev service isn't running. Start it with:

```bash
docker compose up -d roborev
```

## Future Improvements

1. **Dynamic container discovery**: Use docker labels instead of hardcoded names
2. **Embedded agent**: Run a lightweight agent inside the roborev container
3. **Roborev API mode**: Call roborev via HTTP instead of docker exec
4. **Resource limits**: Add CPU/memory limits to prevent roborev from consuming all resources
