# Evolution Agent - Self-Coding/Self-Evolving System
# Based on AGI-Corporation/ralph repository

from .agents import ObserverAgent, ArchitectAgent, AuditorAgent, PlannerAgent
from .sandbox import Sandbox
from .engine import EvolutionEngine
from .version_control import GitManager
from .supervisor import Supervisor
from .epoch_tracker import EpochTracker
from .reporting import EvolutionReporter
from .nanda_bridge import NANDABridge, setup_nanda

__all__ = [
    "ObserverAgent",
    "ArchitectAgent",
    "AuditorAgent",
    "PlannerAgent",
    "Sandbox",
    "EvolutionEngine",
    "GitManager",
    "Supervisor",
    "EpochTracker",
    "EvolutionReporter",
    "NANDABridge",
    "setup_nanda",
]
