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
│   ├── epoch_tracker.py # Epoch and fitness tracking
│   ├── reporting.py     # Extensive reporting and analytics
│   ├── nanda_bridge.py  # NANDA Protocol – skill routing, peer advertisement
│   ├── sandbox.py       # Safe code execution & test runner
│   ├── supervisor.py    # Orchestration of agents + git + skills + NANDA
│   ├── version_control.py # Git integration for safe rollback
│   ├── memory.json      # Long-term memory of successful evolutions
│   └── feature_queue.json # Queue of feature/skill requests
├── skills/              # Pluggable skill agents
│   ├── registry.py      # Skill registry (built-ins + custom)
│   ├── cli.py           # `python -m skills` CLI
│   ├── bitrefill/       # Bitrefill trading skill
│   │   ├── api.py       # Bitrefill v1 REST API client
│   │   └── agents.py    # BitrefillTradingAgent
│   └── x402/            # x402 micropayment skill
│       ├── client.py    # x402-aware HTTP client (EIP-3009 payment flow)
│       └── agents.py    # X402PaymentAgent
├── bin/
│   └── skills.js        # npx shim → python -m skills
├── logs/
│   ├── system.log       # Runtime logs (read by Observer)
│   └── reports/         # Generated evolution reports
├── main_app.py          # The host application (evolved by the system)
├── package.json         # npm package (npx skills)
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

## Interoperability (NANDA Protocol – v2)

The system integrates deeply with the **NANDA Protocol**, enabling full distributed skill-agent coordination:

### What the NANDA Bridge does

| Feature | Description |
|---|---|
| **Node registration** | Publishes this node's capabilities (including all loaded skills) to the network at startup. |
| **Skill advertisement** | When a new skill is loaded, its capabilities are immediately registered on the network so peers can discover them. |
| **Inbound task routing** | Routes incoming NANDA tasks (`bitrefill_trade`, `x402_payment`, `skill_dispatch`, `evolution_mutation`) to the correct local skill agent. |
| **Result broadcasting** | After every skill task, broadcasts the result back to the network for cross-agent observability and downstream chaining. |
| **Supervisor back-reference** | The bridge holds a reference to the Supervisor so external peers can trigger full skill-task pipelines, including memory logging. |

### Task types on the network

| Task type | Routed to |
|---|---|
| `evolution_mutation` | Supervisor bug-fix / planner pipeline |
| `bitrefill_trade` | `BitrefillTradingAgent` |
| `x402_payment` | `X402PaymentAgent` |
| `skill_dispatch` | Any registered skill (by `skill_id` in payload) |

### Routing an incoming task programmatically

```python
from evolution.nanda_bridge import NANDABridge

bridge = supervisor.nanda_bridge

# Route a Bitrefill trade task received from a peer
result = bridge.route_task({
    "task_type": "bitrefill_trade",
    "task_id": "peer-task-001",
    "payload": {
        "skill_id": "bitrefill/agents",
        "context": {"action": "search", "query": "amazon", "country": "US"},
    },
})
```

### Broadcasting a skill task to the network

```python
import asyncio

task_id = asyncio.run(
    bridge.broadcast_skill_task(
        skill_id="x402/agents",
        context={"action": "fetch", "url": "https://api.example.com/premium"},
        name="Fetch premium data",
    )
)
```

---

## Skills System

The Evolution Agent supports a pluggable **skills** architecture that lets you extend the supervisor with external capabilities.

### Adding a skill

```bash
# Via npx (requires Node.js ≥ 14)
npx skills add bitrefill/agents
npx skills add x402/agents

# Or directly via Python
python -m skills add bitrefill/agents
python -m skills list
```

### Available built-in skills

| Skill ID | Description |
|---|---|
| `bitrefill/agents` | Trade on Bitrefill – search gift cards & mobile top-ups, place orders, and track payments using Bitcoin and other cryptocurrencies. |
| `x402/agents` | Autonomous HTTP micropayments via the [x402 protocol](https://www.x402.org). Fetches x402-gated resources by paying USDC on Base (EIP-3009). Simulation mode when no wallet is configured. |

---

### Bitrefill Trading Agent

Set your credentials:

```bash
export BITREFILL_API_KEY="your-api-key"
export BITREFILL_API_SECRET="your-api-secret"   # optional
```

Add a skill task to the feature queue (`evolution/feature_queue.json`):

```json
[
  {
    "type": "skill",
    "skill_id": "bitrefill/agents",
    "name": "Search Amazon gift cards",
    "context": {
      "action": "search",
      "query": "amazon",
      "country": "US"
    }
  }
]
```

The supervisor picks it up on the next cycle, dispatches it to `BitrefillTradingAgent`, and broadcasts the result to the NANDA network.

#### Supported actions

| action | Required context keys | Description |
|---|---|---|
| `search` | `query`, `country` (opt) | Search the Bitrefill catalog |
| `buy` | `product_id`, `value`, `payment_method` (opt), `currency` (opt), `email` (opt), `phone` (opt) | Place a Bitrefill order |
| `status` | `order_id` | Get order status |
| `list_orders` | `limit` (opt), `skip` (opt) | List past orders |
| `balance` | — | Get account balance |

#### Programmatic usage

```python
from skills.bitrefill import BitrefillTradingAgent

agent = BitrefillTradingAgent()

# Search
products = agent.search("netflix", country="US")

# Buy (returns order dict with payment instructions)
order = agent.buy("netflix-us", value=15.0, payment_method="lightning")

# Track
status = agent.get_order_status(order["id"])
```

---

### x402 Payment Agent

The **x402 protocol** (https://www.x402.org) enables HTTP-native stablecoin micropayments.
When a server returns `HTTP 402 Payment Required`, the agent automatically:
1. Parses the payment requirements (network, asset, amount, recipient).
2. Signs an EIP-3009 `transferWithAuthorization` payload.
3. Retries the request with the `X-PAYMENT` header.

Set your wallet credentials for real on-chain payments (omit for simulation mode):

```bash
export X402_PRIVATE_KEY="0x..."           # hex EVM private key
export X402_WALLET_ADDRESS="0x..."        # matching 0x EVM address
```

Add a skill task to the feature queue:

```json
[
  {
    "type": "skill",
    "skill_id": "x402/agents",
    "name": "Fetch premium API data",
    "context": {
      "action": "fetch",
      "url": "https://api.example.com/premium",
      "max_usdc": 0.10
    }
  }
]
```

#### Supported actions

| action | Required context keys | Description |
|---|---|---|
| `fetch` | `url`, `method` (opt), `headers` (opt), `max_usdc` (opt) | Fetch a URL, auto-paying via x402 if required |
| `pay` | `url`, `method` (opt) | Force a paid fetch (no amount limit check) |
| `check` | `url` | Probe a URL for x402 requirements without paying |
| `status` | — | Return wallet and session payment summary |
| `history` | — | Return the session payment ledger |

#### Programmatic usage

```python
from skills.x402 import X402PaymentAgent

agent = X402PaymentAgent(max_auto_pay_usdc=0.50)

# Check if a resource requires payment
info = agent.check("https://api.example.com/premium")
# → {"x402_required": True, "payment_requirements": {...}}

# Fetch with auto-pay
result = agent.fetch("https://api.example.com/premium")
print(result["body"])

# Session summary
print(agent.status())
# → {"simulation_mode": True, "session_total_usdc": 0.000001, ...}
```

---

## Based On

- [AGI-Corporation/ralph](https://github.com/AGI-Corporation/ralph) — The base operational codebase (Body)
- [interplaynetary/playtime](https://github.com/interplaynetary/playtime) — Agent-Native Development Environment concept
- [AGI-Corporation/nanda-sdk](https://github.com/AGI-Corporation/nanda-sdk) — NANDA Protocol for agent interoperability

## License

MIT
