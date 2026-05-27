"""Entry point for worker agent."""

from nd.worker.agent import create_worker_agent


def main():
    """Run the worker agent."""
    app = create_worker_agent()
    print(f"Starting nd worker agent: {app.node_id}")
    print(f"Instance ID: {app.config.agent_instance_id if hasattr(app, 'config') else 'N/A'}")
    print(f"Control plane: {app.agentfield_server}")
    app.run(auto_port=True)


if __name__ == "__main__":
    main()
