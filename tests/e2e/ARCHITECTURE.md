# E2E Testing Architecture

Visual guide to the E2E testing framework architecture.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       E2E Test Environment                       │
│                  (docker-compose.e2e.yml)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    AgentField                            │   │
│  │                 Control Plane                            │   │
│  │              (port 8080)                                 │   │
│  └──────────────────▲──────────────────────▲───────────────┘   │
│                     │                       │                    │
│        ┌────────────┴────────────┐   ┌─────┴──────────┐        │
│        │                          │   │                 │        │
│  ┌─────▼──────────┐     ┌────────▼───▼──────┐   ┌─────▼─────┐ │
│  │  Triage Agent   │     │   Worker Agent     │   │   Kata    │ │
│  │  (port 8001)    │     │   (port 8002)      │   │  Daemon   │ │
│  │                 │     │                    │   │ (loopback)│ │
│  │  - poll         │     │  - claim_task      │   │           │ │
│  │  - classify     │     │  - analyze         │   │  Tasks    │ │
│  │  - create_task  │     │  - execute         │   │  Storage  │ │
│  └────────┬────────┘     │  - roborev         │   └───────────┘ │
│           │              │  - publish         │                  │
│           │              └────────┬───────────┘                  │
│           │                       │                              │
│  ┌────────▼─────────┐    ┌───────▼──────────┐                  │
│  │ Mock Middleman   │    │  Mock GitHub      │                  │
│  │  (port 8091)     │    │  (port 8092)      │                  │
│  │                  │    │                   │                  │
│  │ - Seed comments  │    │ - Capture posts   │                  │
│  │ - Seed issues    │    │ - Verify output   │                  │
│  │ - Query data     │    │                   │                  │
│  └──────────────────┘    └───────────────────┘                  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               Mock GitLab (port 8093)                    │   │
│  │            (Alternative to Mock GitHub)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
         ▲                                              ▲
         │                                              │
         │  Pytest fixtures + HTTP clients              │
         │                                              │
    ┌────┴──────────────────────────────────────────────┴────┐
    │                                                          │
    │               Test Files (pytest)                       │
    │                                                          │
    │  - test_full_e2e.py      (complete flows)               │
    │  - test_triage_e2e.py    (triage isolation)             │
    │  - test_worker_e2e.py    (worker isolation)             │
    │  - test_reasoners_e2e.py (individual reasoners)         │
    │                                                          │
    └──────────────────────────────────────────────────────────┘
```

## Test Flow Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Test Execution Flow                        │
└──────────────────────────────────────────────────────────────┘

1. Setup Phase
   ├─ Start docker-compose
   ├─ Wait for service health (wait-for-services.sh)
   ├─ Load fixtures (conftest.py)
   └─ Initialize clients (mock_middleman, mock_github, etc.)

2. Seed Phase
   ├─ Load test data from fixtures/
   ├─ POST to mock services (/seed/comments, /seed/issues)
   └─ Verify data is seeded

3. Execution Phase
   ├─ Call agent reasoners via e2e_env.call()
   │  ├─ "nd-triage.poll_comments"
   │  ├─ "nd-triage.classify_actionable"
   │  ├─ "nd-worker.claim_task"
   │  ├─ "nd-worker.analyze_task"
   │  └─ etc.
   │
   └─ Agents process requests
      ├─ Triage creates tasks in kata
      ├─ Worker claims and executes
      └─ Worker posts to mock platforms

4. Verification Phase
   ├─ Query kata for task state
   ├─ Query mocks for posted data (GET /verify)
   ├─ Assert expected outcomes
   └─ Check error conditions

5. Teardown Phase
   ├─ Reset mocks (POST /reset)
   ├─ Collect logs (if failure)
   └─ Stop docker-compose (docker-compose down -v)
```

## Test Levels

```
┌─────────────────────────────────────────────────────────────┐
│                     Test Pyramid                             │
└─────────────────────────────────────────────────────────────┘

                         ▲
                        ╱ ╲
                       ╱   ╲     Full E2E (test_full_e2e.py)
                      ╱     ╲    - Complete workflows
                     ╱       ╲   - All agents + mocks
                    ╱─────────╲  - Slowest, highest confidence
                   ╱           ╲
                  ╱             ╲
                 ╱               ╲ Agent-Specific (test_*_e2e.py)
                ╱                 ╲ - Single agent focus
               ╱                   ╲ - Partial mocks
              ╱                     ╲ - Medium speed
             ╱───────────────────────╲
            ╱                         ╲
           ╱                           ╲
          ╱                             ╲ Reasoner-Level
         ╱                               ╲ (test_reasoners_e2e.py)
        ╱                                 ╲ - Individual functions
       ╱                                   ╲ - Fast, focused
      ╱─────────────────────────────────────╲ - Many tests
     ╱                                       ╲
    ╱_________________________________________╲

```

## Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                  Typical E2E Test Data Flow                   │
└──────────────────────────────────────────────────────────────┘

1. Seed Test Data
   ┌────────────────┐
   │  Test Fixtures │
   │ (JSON files)   │
   └───────┬────────┘
           │
           ▼
   ┌────────────────┐    POST /seed/comments
   │    Pytest      ├───────────────────────►
   │   Test Case    │    POST /seed/issues
   └────────────────┘
           │
           │
           ▼
   ┌────────────────┐
   │ Mock Middleman │
   │   (stores in   │
   │    memory)     │
   └────────────────┘

2. Trigger Agent
   ┌────────────────┐
   │    Pytest      │  e2e_env.call("nd-triage.poll_comments")
   │   Test Case    ├────────────────────────────────────────►
   └────────────────┘
           │
           ▼
   ┌────────────────┐    GET /comments
   │ Triage Agent   ├──────────────────►┌────────────────┐
   │                │                    │ Mock Middleman │
   │ - Classify     │◄──────────────────┤                │
   │ - Create Task  │  Returns comments  └────────────────┘
   └───────┬────────┘
           │
           │ kata.create()
           ▼
   ┌────────────────┐
   │  Kata Daemon   │
   │  (task storage)│
   └────────────────┘

3. Worker Processing
   ┌────────────────┐
   │    Pytest      │  e2e_env.call("nd-worker.claim_task")
   │   Test Case    ├────────────────────────────────────────►
   └────────────────┘
           │
           ▼
   ┌────────────────┐    kata.ready()
   │ Worker Agent   ├──────────────────►┌────────────────┐
   │                │                    │  Kata Daemon   │
   │ - Claim        │◄──────────────────┤                │
   │ - Analyze      │  Returns task      └────────────────┘
   │ - Execute      │
   │ - Post         │
   └───────┬────────┘
           │
           │ POST /repos/.../comments
           ▼
   ┌────────────────┐
   │  Mock GitHub   │
   │ (captures post)│
   └────────────────┘

4. Verification
   ┌────────────────┐
   │    Pytest      │  kata_client.list_tasks()
   │   Test Case    ├────────────────────────────►┌────────────────┐
   │                │                              │  Kata Daemon   │
   │  - Check tasks │◄────────────────────────────┤                │
   │  - Verify post │  Returns tasks               └────────────────┘
   │                │
   │                │  GET /verify
   │                ├────────────────────────────►┌────────────────┐
   │                │                              │  Mock GitHub   │
   │                │◄────────────────────────────┤                │
   └────────────────┘  Returns posted comments     └────────────────┘
```

## Mock Service API

```
┌──────────────────────────────────────────────────────────────┐
│                    Mock Middleman API                         │
├──────────────────────────────────────────────────────────────┤
│  GET  /health                         → Health check          │
│  GET  /comments?since=...&user=...    → Get comments          │
│  GET  /issues/assigned/{username}     → Get assigned issues   │
│  POST /seed/comments                  → Load test comments    │
│  POST /seed/issues                    → Load test issues      │
│  POST /reset                          → Clear all data        │
│  GET  /                               → Service info          │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                     Mock GitHub API                           │
├──────────────────────────────────────────────────────────────┤
│  GET  /health                                → Health check   │
│  POST /repos/{owner}/{repo}/issues/{n}/...   → Post comment   │
│  POST /repos/{owner}/{repo}/pulls/{n}/...    → Post comment   │
│  GET  /repos/{owner}/{repo}/pulls/{n}        → Get PR         │
│  POST /repos/{owner}/{repo}/pulls            → Create PR      │
│  GET  /verify                                → Get all posts  │
│  POST /reset                                 → Clear data     │
│  GET  /                                      → Service info   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                     Mock GitLab API                           │
├──────────────────────────────────────────────────────────────┤
│  GET  /health                                → Health check   │
│  POST /api/v4/projects/{id}/merge_requests/{mr}/... → Note    │
│  GET  /api/v4/projects/{id}/merge_requests/{mr}  → Get MR    │
│  POST /api/v4/projects/{id}/merge_requests   → Create MR     │
│  GET  /verify                                → Get all notes  │
│  POST /reset                                 → Clear data     │
│  GET  /                                      → Service info   │
└──────────────────────────────────────────────────────────────┘
```

## Development Workflow

```
┌──────────────────────────────────────────────────────────────┐
│              Fast Iteration Workflow                          │
└──────────────────────────────────────────────────────────────┘

┌─────────────────────────┐
│  1. Start main compose  │  docker-compose up -d
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  2. Make code changes   │  Edit nd/worker/agent.py
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  3. Recreate agent      │  docker-compose up -d --force-recreate worker-1
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  4. Run E2E tests       │  pytest tests/e2e/ -v --use-running-agent
└────────────┬────────────┘
             │
             ▼
      ┌──────┴──────┐
      │   Pass?     │
      └──┬──────┬───┘
         │      │
    Yes  │      │ No
         │      │
         ▼      ▼
    ┌─────┐  ┌──────────────────┐
    │Done │  │Back to step 2    │
    └─────┘  │(iterate quickly) │
             └──────────────────┘

Benefits:
- No docker-compose startup delay
- Fast feedback loop (< 10 seconds)
- Test against real agent behavior
- Easy debugging with live logs
```

## File Organization

```
tests/e2e/
│
├── Infrastructure
│   ├── docker-compose.e2e.yml    # Service definitions
│   ├── conftest.py               # Pytest fixtures
│   ├── pytest.ini                # Pytest config
│   └── .gitignore                # Ignore artifacts
│
├── Tests
│   ├── test_full_e2e.py          # Complete workflows
│   ├── test_triage_e2e.py        # Triage isolation
│   ├── test_worker_e2e.py        # Worker isolation
│   ├── test_reasoners_e2e.py     # Individual reasoners
│   └── example_test.py           # Annotated examples
│
├── Mocks (3 services)
│   ├── mock_middleman/
│   │   ├── Dockerfile
│   │   └── app.py
│   ├── mock_github/
│   │   ├── Dockerfile
│   │   └── app.py
│   └── mock_gitlab/
│       ├── Dockerfile
│       └── app.py
│
├── Fixtures (test data)
│   ├── comments.json             # Sample comments
│   ├── issues.json               # Sample issues
│   └── scenarios/                # Complex scenarios
│       ├── simple_request.json
│       ├── complex_refactor.json
│       └── issue_flow.json
│
├── Scripts (automation)
│   ├── run-e2e-tests.sh          # Full suite
│   ├── test-running-agent.sh     # Fast iteration
│   └── wait-for-services.sh      # Health checks
│
└── Documentation
    ├── README.md                  # Complete guide
    ├── QUICKSTART.md              # Getting started
    └── ARCHITECTURE.md            # This file
```
