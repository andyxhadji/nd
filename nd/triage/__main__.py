"""Entry point for triage agent."""

from nd.config import config
from nd.triage.agent import create_triage_agent


def main():
    """Run the triage agent."""
    app = create_triage_agent()
    print(f"Starting nd triage agent: {app.node_id}")
    print(f"Control plane: {app.agentfield_server}")
    if config.agent_port:
        app.run(host="0.0.0.0", port=config.agent_port, auto_port=False)
    else:
        app.run(auto_port=True)


if __name__ == "__main__":
    main()
