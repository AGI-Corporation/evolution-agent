# 🧬 Evolution Agent: The Self-Actualizing Codebase

[![Evolution Cycle](https://img.shields.io/badge/Evolution-Continuous-brightgreen?style=for-the-badge&logo=dna)](https://github.com/AGI-Corporation/evolution-agent)
[![NANDA Interop](https://img.shields.io/badge/NANDA-Bridge_Active-blue?style=for-the-badge&logo=intercom)](https://github.com/AGI-Corporation/nanda-sdk)
[![Voice Interface](https://img.shields.io/badge/Interface-Voice_Native-orange?style=for-the-badge&logo=microphone)](https://github.com/AGI-Corporation/evolution-agent)

> "The first step toward true AGI is a system that can reason about, repair, and expand its own architecture."

Evolution Agent is a **Self-Coding / Self-Evolving meta-framework** built upon the [AGI-Corporation/ralph](https://github.com/AGI-Corporation/ralph) operative core. It transforms a static repository into a living organism that autonomously monitors its own health, patches vulnerabilities, and implements new features through a high-fidelity multi-agent feedback loop.

---

## 🐝 Architecture: "The Ralph Hive"

The system operates as a decentralized hive of specialized agents, each fine-tuned for a specific stage of the developmental lifecycle.

| Agent | Metaphor | Primary Mission | Color Code |
| :--- | :--- | :--- | :--- |
| **Observer** | 👁️ The Senses | Scans logs & metrics to detect anomalies. | 🔵 **Azure** |
| **Architect** | 🧠 The Brain | Designs high-level patches and feature implementations. | 🔴 **Crimson** |
| **Auditor** | 🛡️ The Immune System | Validates logic and enforces security guardrails. | 🟢 **Emerald** |
| **Planner** | 🚀 The Growth Engine | Deconstructs goals into actionable sprints. | 🟡 **Amber** |

---

## 🛠️ The Evolution Lifecycle

```mermaid
graph LR
    subgraph Sensory_Input [Sensory Input]
    A[Observer] -- "Detects Error" --> B{Architect}
    end

    subgraph Neural_Processing [Neural Processing]
    B -- "Designs Patch" --> C[Auditor]
    C -- "Fails Validation" --> B
    end

    subgraph Physical_Action [Physical Action]
    C -- "Passes Tests" --> D[GitManager]
    D -- "Commits to fix/ branch" --> E[EpochTracker]
    end

    subgraph Genetic_Logging [Genetic Logging]
    E -- "Updates Hall of Fame" --> F[EvolutionReporter]
    F -- "Generates Analytics" --> A
    end

    style A fill:#e1f5fe,stroke:#01579b
    style B fill:#ffebee,stroke:#b71c1c
    style C fill:#e8f5e9,stroke:#1b5e20
    style D fill:#f3e5f5,stroke:#4a148c
    style E fill:#fff3e0,stroke:#e65100
    style F fill:#f1f8e9,stroke:#33691e
```

---

## 🎙️ Voice Coding Agent (The "No-Keyboard" Interface)

Step into the future of development with a voice-native interface that bridges human intent and machine execution.

### ✨ Vivid Workflow Example

```mermaid
sequenceDiagram
    participant User
    participant Whisper as 🎙️ Whisper STT
    participant GPT as 🧠 GPT-4o
    participant TTS as 🔊 OpenAI TTS
    participant Disk as 💾 Disk

    User->>Whisper: "Add an async health route"
    Whisper->>GPT: Transcribed Intent
    Note right of GPT: Architecting Code...
    GPT->>User: Display Generated Code
    GPT->>TTS: "Adding /health route to main_app.py"
    TTS-->>User: (Spoken Explanation)
    User->>Disk: Confirm & Save
```

---

## 🧬 Core Evolution Components

- **Epoch Tracker** (`evolution/epoch_tracker.py`): The system's **"DNA Ledger."** It versions every mutation, calculates fitness scores, and maintains the **"Hall of Fame"** of superior agent configurations.
- **Evolution Reporter** (`evolution/reporting.py`): Generates vivid, data-driven analytics on mutation lineages, heatmaps of code changes, and performance deltas across generations.
- **NANDA Bridge** (`evolution/nanda_bridge.py`): Standardizes interoperability using the **NANDA Protocol**, allowing the hive to collaborate with external agent networks.

---

## 📂 Project Anatomy

```text
evolution-agent/
├── evolution/             # 🧠 The "Prefrontal Cortex"
│   ├── agents.py          # Logic for Observer, Architect, Auditor, Planner
│   ├── engine.py          # 💓 The heartbeat of the evolution loop
│   ├── epoch_tracker.py   # 🧬 Fitness scoring and lineage tracking
│   ├── nanda_bridge.py    # 🌐 Cross-agent interoperability layer
│   └── sandbox.py         # 🛡️ Secure execution environment
├── logs/                  # 👁️ System sensory data
├── main_app.py            # 🍄 The target organism (being evolved)
└── voice_agent.py         # 🎙️ The voice-interactive gateway
```

---

## 🚀 Quick Start: Ignite the Hive

### 1. Environmental Setup
```bash
pip install -r requirements.txt
export OPENAI_API_KEY="your-key-here"
```

### 2. Launch the Voice Agent
```bash
python voice_agent.py --seconds 15
```

### 3. Start Autonomously
```bash
# Force the system to refactor itself for performance
python -m cli.evolve --task "Optimize loop latency in engine.py" --pop_size 8
```

---

## 🛡️ Safety & Integrity

- **Atomic Commits:** Every evolution occurs on an isolated `fix/` or `feat/` branch.
- **Automated Rollback:** If a mutation fails runtime tests, the system triggers an immediate `git reset --hard` to the last known-good state.
- **Sandboxed Validation:** No code touches the `main` branch without passing the Auditor's automated test suite.

---

Maintained by **AGI Corporation** — *Pioneers in Self-Evolving Agentic Infrastructure.*
