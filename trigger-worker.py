#!/usr/bin/env python3
"""Trigger worker claim_task via kata CLI to force execution."""

import subprocess
import sys

# First check if there's an unowned task
result = subprocess.run(
    [
        "docker",
        "exec",
        "hyper-furniture-kata-daemon-1",
        "sh",
        "-c",
        "cd /kata-home && kata list --label nd --unowned",
    ],
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    print(f"Error listing tasks: {result.stderr}")
    sys.exit(1)

if not result.stdout.strip():
    print("No unowned nd tasks found")
    sys.exit(0)

print(f"Found unowned tasks:\n{result.stdout}")

# Manually claim the task
task_id = result.stdout.split()[0]  # First column is task ID
print(f"\nClaiming task {task_id} for worker-2...")

result = subprocess.run(
    [
        "docker",
        "exec",
        "hyper-furniture-kata-daemon-1",
        "sh",
        "-c",
        f"cd /kata-home && kata assign {task_id} worker-2",
    ],
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    print(f"Error assigning task: {result.stderr}")
    sys.exit(1)

print(f"Assigned: {result.stdout}")

# Add in-progress label
subprocess.run(
    [
        "docker",
        "exec",
        "hyper-furniture-kata-daemon-1",
        "sh",
        "-c",
        f"cd /kata-home && kata label {task_id} in-progress",
    ],
    capture_output=True,
)

# Now the worker should pick it up on its next poll
# OR we trigger process_task manually by getting task details
print("\nTask is assigned to worker-2. Checking if worker can process it...")
print("Monitor at: http://localhost:8081/ui")
print("Dashboard at: http://localhost:3000")
