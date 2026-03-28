# evolution/epoch_tracker.py
# Tracks agent lifecycle, fitness scores, and Hall of Fame across epochs.
# Integrates with Supervisor, GitManager, and memory.json patterns.

import os
import json
import logging
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class AgentVersion:
    """Represents a specific versioned snapshot of an agent in the evolutionary loop."""
    version_id: str
    epoch: int
    parent_id: Optional[str]       # Lineage tracking
    mutation_params: Dict           # Hyperparameters / architectural mutations
    fitness_score: float = 0.0
    status: str = "created"         # created | tested | failed

    def __lt__(self, other):
        return self.fitness_score < other.fitness_score


# ---------------------------------------------------------------------------
# EpochTracker
# ---------------------------------------------------------------------------

class EpochTracker:
    """
    Tracks the full evolution lifecycle across epochs.

    Responsibilities:
      - Register new agent versions (mutations / fresh spawns)
      - Log fitness scores after evaluation
      - Select top-N survivors (Hall of Fame) for the next generation
      - Checkpoint state to epoch_log.json (mirrors memory.json pattern)

    Integrates with:
      - Supervisor  -> call start_epoch() at the top of each run() cycle
      - GitManager  -> pass branch names via mutation_params for lineage
      - memory.json -> save_checkpoint() appends to the shared memory file
    """

    CHECKPOINT_FILE = "epoch_log.json"
    MEMORY_KEY = "epoch_checkpoints"

    def __init__(self, project_root: str, memory_path: Optional[str] = None):
        self.project_root = project_root
        self.current_epoch: int = 0
        self.population: Dict[str, AgentVersion] = {}
        self.history: List[Dict] = []

        # Default: store alongside evolution/memory.json
        self.memory_path = memory_path or os.path.join(
            project_root, "evolution", "memory.json"
        )
        self.checkpoint_path = os.path.join(
            project_root, "evolution", self.CHECKPOINT_FILE
        )
        self._load_state()

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load_state(self):
        """Resume from a previous checkpoint if one exists."""
        try:
            with open(self.checkpoint_path, "r") as f:
                data = json.load(f)
            self.current_epoch = data.get("current_epoch", 0)
            self.history = data.get("history", [])
            print(f"[EpochTracker] Resumed from Epoch {self.current_epoch}.")
            logger.debug("[EpochTracker] Loaded %d history records from %s", len(self.history), self.checkpoint_path)
        except FileNotFoundError:
            print("[EpochTracker] No prior checkpoint found. Starting fresh.")

    def save_checkpoint(self):
        """
        Persist current state to epoch_log.json and append a summary
        entry to memory.json so the Supervisor can reference it.
        """
        top_versions = [asdict(a) for a in self.get_top_tested_versions(5)]

        checkpoint = {
            "current_epoch": self.current_epoch,
            "timestamp": datetime.now().isoformat(),
            "population_size": len(self.population),
            "top_versions": top_versions,
            "history": self.history,
        }

        # Write dedicated checkpoint file
        os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
        with open(self.checkpoint_path, "w") as f:
            json.dump(checkpoint, f, indent=4)

        # Append summary to shared memory.json (Supervisor-compatible)
        self._append_to_memory({
            "type": "epoch_checkpoint",
            "epoch": self.current_epoch,
            "timestamp": datetime.now().isoformat(),
            "population_size": len(self.population),
            "top_version_ids": [v["version_id"] for v in top_versions],
            "status": "success",
        })

        print(f"[EpochTracker] Checkpoint saved for Epoch {self.current_epoch}.")

    def _append_to_memory(self, entry: Dict):
        """Append an entry to the shared memory.json file."""
        try:
            if os.path.exists(self.memory_path):
                with open(self.memory_path, "r") as f:
                    data = json.load(f)
            else:
                data = []

            data.append(entry)

            with open(self.memory_path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[EpochTracker] Memory write error: {e}")

    # ------------------------------------------------------------------
    # Epoch lifecycle
    # ------------------------------------------------------------------

    def start_epoch(self):
        """Increment the epoch counter and reset the active population."""
        self.current_epoch += 1
        self.population = {}
        print(f"\n{'='*50}")
        print(f"  Epoch {self.current_epoch} Started  |  {datetime.now().isoformat()}")
        print(f"{'='*50}")

    # ------------------------------------------------------------------
    # Population management
    # ------------------------------------------------------------------

    def register_agent(
        self,
        parent_id: Optional[str],
        mutation_params: Dict,
    ) -> AgentVersion:
        """
        Register a new agent version for this epoch.

        Args:
            parent_id:       version_id of the parent agent (None for seed agents).
            mutation_params: Dict of hyperparameters, architecture tags, git branch, etc.

        Returns:
            The newly created AgentVersion object.
        """
        version_id = f"agent_{str(uuid.uuid4())[:8]}_e{self.current_epoch}"

        agent = AgentVersion(
            version_id=version_id,
            epoch=self.current_epoch,
            parent_id=parent_id,
            mutation_params=mutation_params,
        )

        self.population[version_id] = agent
        print(f"[EpochTracker] Registered: {version_id}  (parent={parent_id})")
        logger.debug("[EpochTracker] Agent params: %s", mutation_params)
        return agent

    def log_performance(
        self,
        version_id: str,
        score: float,
        status: str = "tested",
    ):
        """
        Record a fitness score for an agent after evaluation.

        Args:
            version_id: The agent's unique ID.
            score:      Normalised fitness score (0.0 – 1.0 recommended).
            status:     'tested' on success, 'failed' on evaluation error.
        """
        if version_id not in self.population:
            print(f"[EpochTracker] ERROR: Unknown agent {version_id}.")
            return

        agent = self.population[version_id]
        agent.fitness_score = score
        agent.status = status

        record = {**asdict(agent), "logged_at": datetime.now().isoformat()}
        self.history.append(record)
        print(f"[EpochTracker] Logged: {version_id} | Score: {score:.4f} | Status: {status}")
        logger.debug("[EpochTracker] Performance record: %s", record)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def get_top_tested_versions(self, top_n: int = 3) -> List[AgentVersion]:
        """
        Return the top-N fittest agents that completed testing successfully.
        These become the parents for the next epoch (natural selection).

        Searches the current population first, then falls back to history
        so callers can retrieve Hall-of-Fame survivors across epochs.
        """
        # Prefer current population
        tested = [a for a in self.population.values() if a.status == "tested"]

        # Supplement with historical records if needed
        if len(tested) < top_n:
            seen = {a.version_id for a in tested}
            for record in reversed(self.history):
                if record.get("status") == "tested" and record["version_id"] not in seen:
                    tested.append(AgentVersion(**{
                        k: record[k] for k in AgentVersion.__dataclass_fields__
                    }))
                    seen.add(record["version_id"])

        sorted_agents = sorted(tested, key=lambda a: a.fitness_score, reverse=True)
        return sorted_agents[:top_n]

    def print_leaderboard(self, top_n: int = 5):
        """Pretty-print the Hall of Fame for the current epoch."""
        top = self.get_top_tested_versions(top_n)
        print(f"\n{'='*50}")
        print(f"  HALL OF FAME  |  Epoch {self.current_epoch}")
        print(f"{'='*50}")
        if not top:
            print("  No tested agents yet.")
        for rank, agent in enumerate(top, 1):
            parent_tag = f"← {agent.parent_id}" if agent.parent_id else "seed"
            print(
                f"  {rank}. {agent.version_id}"
                f"  Score: {agent.fitness_score:.4f}"
                f"  [{parent_tag}]"
            )
        print(f"{'='*50}\n")


# ---------------------------------------------------------------------------
# Simulation helpers (replace with real evaluation harness)
# ---------------------------------------------------------------------------

def simulate_agent_evaluation(agent: AgentVersion) -> float:
    """
    Mock fitness evaluation.
    Replace this with your actual test-suite runner / LLM scorer.
    """
    import random
    base = random.uniform(0.50, 0.75)

    if agent.mutation_params.get("learning_rate") == "adaptive":
        base += 0.15
    if agent.mutation_params.get("architecture") == "transformer_v2":
        base += 0.10
    if agent.mutation_params.get("memory") == "long_term":
        base += 0.05

    return min(base, 1.0)


# ---------------------------------------------------------------------------
# Demo evolution loop
# ---------------------------------------------------------------------------

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tracker = EpochTracker(project_root)

    # ── Epoch 1: Seed population ─────────────────────────────────────────────
    tracker.start_epoch()

    seed_params = {"learning_rate": "static", "architecture": "basic_rnn", "memory": "none"}
    for _ in range(5):
        agent = tracker.register_agent(parent_id=None, mutation_params=seed_params.copy())
        score = simulate_agent_evaluation(agent)
        tracker.log_performance(agent.version_id, score)

    tracker.print_leaderboard()
    survivors = tracker.get_top_tested_versions(top_n=2)
    tracker.save_checkpoint()

    # ── Epoch 2: Mutate survivors ────────────────────────────────────────────
    tracker.start_epoch()
    print("[Evolution] Mutating top survivors into next generation...")

    for parent in survivors:
        child_params = {**parent.mutation_params, "learning_rate": "adaptive"}
        child = tracker.register_agent(
            parent_id=parent.version_id,
            mutation_params=child_params,
        )
        score = simulate_agent_evaluation(child)
        tracker.log_performance(child.version_id, score)

    tracker.print_leaderboard()
    tracker.save_checkpoint()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Epoch Tracker demo")
    parser.add_argument(
        "--debug", "-debug",
        action="store_true",
        help="Enable verbose debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    main()
