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

A **Supervisor** orchestrates all agents, and a **GitManager** ensures every evolution is committed, reversible, and auditable.

---

## Project Structure

```
evolution-agent/
├── evolution/                 # Core self-evolution module
│   ├── __init__.py
│   ├── agents.py              # Observer, Architect, Auditor, Planner agents
│   ├── engine.py              # Main loop controller
│   ├── sandbox.py             # Safe code execution & test runner
│   ├── supervisor.py          # Orchestration of agents + git
│   ├── version_control.py     # Git integration for safe rollback
│   ├── memory.json            # Long-term memory of successful evolutions
│   └── feature_queue.json     # Queue of feature requests for the Planner
├── logs/
│   └── system.log             # Runtime logs (read by Observer)
├── main_app.py                # The host application (evolved by the system)
├── requirements.txt
└── README.md
```

---

## How It Works

### The Evolution Loop

1. **Ingest** — The Observer reads `logs/system.log` (errors) and `evolution/feature_queue.json` (goals).
2. **Reason** — Agents decide what code needs to be written or fixed.
3. **Verify** — The Auditor checks syntax; the Sandbox runs tests.
4. **Persist** — GitManager commits changes, making evolutions permanent and reversible.
5. **Repeat** — The loop continues, continuously improving the codebase.

### Self-Fix Flow

```
Cycle:
  ObserverAgent  →  reads system.log  →  detects ZeroDivisionError
  ArchitectAgent →  reads main_app.py →  LLM generates fix patch
  AuditorAgent   →  validates syntax  →  approves patch
  Sandbox        →  runs pytest       →  tests pass
  GitManager     →  commits fix       →  evolution logged to memory.json
```

### Feature Request Flow

Drop a request into `evolution/feature_queue.json`:

```json
[
  {
    "name": "add_logging",
    "description": "Add a function to log system status to logs/status.log with a timestamp."
  }
]
```

The Planner agent will implement it, the Sandbox will verify it, and GitManager will commit it — all automatically.

---

## Runtime Context Bridge

Based on the `interplaynetary/playtime` concept, this repo also includes a `runtime_context_bridge` tool that allows agents and humans to inspect live runtime state before generating code:

- `source_snapshot` — current code block for a given scope
- `runtime_values` — actual variable values at execution time
- `dependency_map` — what modules/functions the scope depends on
- `diff_context` — suggested injection points for new code

This prevents "blind coding" — agents always have a full mental model of the current state before proposing changes.

---

## Quick Start

### Prerequisites

```bash
pip install -r requirements.txt
```

Set your LLM API key:

```bash
export OPENAI_API_KEY=your_key_here
```

### Run the Host App (to generate an error log)

```bash
python main_app.py 2> logs/system.log
```

### Start the Evolution Engine

```bash
python -m evolution.supervisor
```

---

## Safety Features

- **Git Branching** — Every evolution runs on a dedicated `fix/<timestamp>` branch.
- **Sandbox Testing** — Patches are syntax-checked and pytest-validated before applying.
- **Rollback** — Failed evolutions trigger `git reset --hard HEAD~1` automatically.
- **Memory Bank** — `memory.json` logs all successful evolutions for future reference.
- **Human-in-the-Loop (optional)** — The Auditor can be configured to send Slack/webhook approval requests before applying critical changes.

---

## Based On

- [AGI-Corporation/ralph](https://github.com/AGI-Corporation/ralph) — The base operational codebase (Body)
- [interplaynetary/playtime](https://github.com/interplaynetary/playtime) — Agent-Native Development Environment concept

---

## License

MIT
