# Evolution Agent

A **Self-Coding / Self-Evolving System** built on the [AGI-Corporation/ralph](https://github.com/AGI-Corporation/ralph) repository. This system uses a multi-agent loop to autonomously monitor, repair, and grow its own codebase — without human intervention.

Inspired by the [interplaynetary/playtime](https://github.com/interplaynetary/playtime) Agent-Native Development Environment concept, which bridges the gap between runtime state and code generation via a `runtime_context_bridge` tool.

---

## Architecture: "The Ralph Hive"

Three specialized agents operate in a continuous loop:

| Agent | Role | Responsibility |
|---|---|---|
| **Observer** | The Senses | Monitors logs, detects errors and anomalies |
| **Architect** | The Brain | Reads source code, generates fix patches via LLM |
| **Auditor** | The Immune System | Validates patches, runs tests in sandbox |
| **Planner** | The Growth Engine | Implements new features from the feature queue |

A **Supervisor** orchestrates all agents, supported by a **GitManager** for version control and a **NANDABridge** for distributed interoperability.

## Core Evolution Components

- **Epoch Tracker** (`evolution/epoch_tracker.py`): Tracks agent lifecycle, fitness scores, and "Hall of Fame" across evolution epochs.
- **Evolution Reporter** (`evolution/reporting.py`): Provides extensive analytics on mutations, success rates, and lineage performance.
- **NANDA Bridge** (`evolution/nanda_bridge.py`): Integrates with the [NANDA Protocol](https://github.com/AGI-Corporation/nanda-sdk) for distributed analysis and cross-agent communication.

## Project Structure

```text
evolution-agent/
├── evolution/           # Core self-evolution module
│   ├── __init__.py
│   ├── agents.py        # Observer, Architect, Auditor, Planner agents
│   ├── engine.py        # Main loop controller
│   ├── epoch_tracker.py # NEW: Epoch and fitness tracking
│   ├── reporting.py     # NEW: Extensive reporting and analytics
│   ├── nanda_bridge.py  # NEW: NANDA Protocol interoperability
│   ├── sandbox.py       # Safe code execution & test runner
│   ├── supervisor.py    # Orchestration of agents + git
│   ├── version_control.py # Git integration for safe rollback
│   ├── memory.json      # Long-term memory of successful evolutions
│   └── feature_queue.json # Queue of feature requests for the Planner
├── logs/
│   ├── system.log       # Runtime logs (read by Observer)
│   └── reports/         # Generated evolution reports
├── main_app.py          # The host application (evolved by the system)
├── requirements.txt
└── README.md
```

## How It Works

### The Evolution Loop

1. **Ingest** — The Observer reads `logs/system.log` (errors) and `evolution/feature_queue.json` (goals).
2. **Reason** — Agents decide what code needs to be written or fixed.
3. **Verify** — The Auditor checks syntax; the Sandbox runs tests.
4. **Persist** — GitManager commits changes, and EpochTracker logs the cycle's fitness.
5. **Report** — EvolutionReporter generates performance analytics.
6. **Repeat** — The loop continues, continuously improving the codebase.

## Interoperability (NANDA Protocol)

The system now supports the **NANDA Protocol**, allowing it to collaborate with external agents (like Max Health or CMMC compliance agents). By broadcasting mutation tasks, the Evolution Agent can leverage a distributed network for complex analysis.

---

## Safety Features

- **Git Branching** — Every evolution runs on a dedicated `fix/` branch.
- **Sandbox Testing** — Patches are syntax-checked and pytest-validated before applying.
- **Rollback** — Failed evolutions trigger `git reset --hard HEAD~1` automatically.
- **Memory Bank** — `memory.json` logs all successful evolutions for future reference.

## Based On

- [AGI-Corporation/ralph](https://github.com/AGI-Corporation/ralph) — The base operational codebase (Body)
- [interplaynetary/playtime](https://github.com/interplaynetary/playtime) — Agent-Native Development Environment concept
- [AGI-Corporation/nanda-sdk](https://github.com/AGI-Corporation/nanda-sdk) — NANDA Protocol for agent interoperability

## License

MIT
