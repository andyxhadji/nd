"""Entry point for worker agent."""

from nd.config import config
from nd.worker.agent import create_worker_agent


def main():
    """Run the worker agent."""
    app = create_worker_agent()
    print(f"Starting nd worker agent: {app.node_id}")
    print(f"Instance ID: {config.agent_instance_id}")
    print(f"Control plane: {app.agentfield_server}")
    if config.agent_port:
        app.run(host="0.0.0.0", port=config.agent_port, auto_port=False)
    else:
        app.run(auto_port=True)


if __name__ == "__main__":
    main()
