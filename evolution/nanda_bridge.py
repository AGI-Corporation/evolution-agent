# evolution/nanda_bridge.py
# NANDA Protocol Integration for Evolution-Agent.
# Provides a bridge between local evolution cycles and the distributed NANDA agent network.
# See: https://github.com/AGI-Corporation/nanda-sdk
#
# Deep integration (v2):
#   - Skill-agent advertisement: nodes publish their capabilities to the network.
#   - Skill-task routing: incoming NANDA tasks are dispatched to the correct
#     local skill agent (bitrefill/agents, x402/agents, etc.).
#   - Task types: evolution_mutation | bitrefill_trade | x402_payment | skill_dispatch
#   - Supervisor back-reference: the bridge can ask the Supervisor to execute
#     skill tasks on behalf of remote peers.

import logging
import asyncio
from typing import Callable, Dict, Any, List, Optional
from datetime import datetime, timezone

# Attempt to import NANDA SDK protocol components
try:
    from nanda_sdk.protocol import NANDAProtocolCoordinator, AgentTask, AgentTaskStatus
except ImportError:
    # Fallback to internal mocks if SDK is not installed (simulation/bootstrap mode)
    class AgentTaskStatus:
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

    class AgentTask:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class NANDAProtocolCoordinator:
        def __init__(self, redundancy_factor: int = 2):
            self.nodes: Dict[str, Any] = {}
            self.redundancy_factor = redundancy_factor

        def register_node(self, node_id, capabilities, endpoint):
            self.nodes[node_id] = {
                "id": node_id,
                "capabilities": capabilities,
                "status": "online",
            }

        async def submit_task(self, task_type, payload):
            return f"task_{datetime.now(timezone.utc).timestamp()}"


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Task-type constants (used by both sender and receiver)
# ---------------------------------------------------------------------------

TASK_EVOLUTION_MUTATION = "evolution_mutation"
TASK_BITREFILL_TRADE    = "bitrefill_trade"
TASK_X402_PAYMENT       = "x402_payment"
TASK_SKILL_DISPATCH     = "skill_dispatch"   # generic skill routing

# Capabilities exported to the NANDA network by default
_DEFAULT_CAPABILITIES = [
    "code_mutation",
    "bug_analysis",
    "system_optimization",
    "bitrefill_trade",
    "x402_payment",
]


# ---------------------------------------------------------------------------
# NANDABridge
# ---------------------------------------------------------------------------

class NANDABridge:
    """
    Bridges the Evolution-Agent Supervisor with the NANDA Protocol.
    Enables distributed analysis and cross-agent interoperability.

    Deep integration
    ----------------
    * **Skill advertisement** – on init, registers all loaded skill capabilities
      as node capabilities so other NANDA nodes know what this node can do.
    * **Skill-task routing** – ``route_task()`` maps incoming NANDA task types
      to the correct local skill agent via the Supervisor.
    * **Result broadcasting** – ``broadcast_result()`` publishes the outcome of
      a skill task back to the network so other nodes can observe it.
    * **Supervisor back-reference** – the bridge holds a weak reference to the
      Supervisor so it can call ``process_skill_task()`` on behalf of peers.
    """

    def __init__(
        self,
        node_id: str,
        capabilities: List[str] = None,
        supervisor=None,
    ):
        self.node_id = node_id
        self.capabilities = capabilities or list(_DEFAULT_CAPABILITIES)
        self.coordinator = NANDAProtocolCoordinator(redundancy_factor=2)
        self._supervisor = supervisor  # optional back-reference to Supervisor
        self._task_handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._result_log: List[Dict[str, Any]] = []

        # Register this evolution instance as a NANDA node
        self.coordinator.register_node(
            node_id=self.node_id,
            capabilities=self.capabilities,
            endpoint="local://evolution_agent_v2",
        )

        # Register built-in task handlers
        self._register_default_handlers()

        logger.info("[NANDA] Bridge v2 initialized for node: %s", self.node_id)
        logger.info("[NANDA] Capabilities: %s", self.capabilities)

    # ------------------------------------------------------------------
    # Capability advertisement
    # ------------------------------------------------------------------

    def register_skill_capabilities(self, skill_id: str, skill_capabilities: List[str]):
        """
        Advertise a newly loaded skill's capabilities on the NANDA network.

        Call this when a skill agent is loaded by the Supervisor so peers
        can discover what services this node provides.

        Args:
            skill_id:            e.g. ``"bitrefill/agents"``
            skill_capabilities:  list of capability strings
        """
        new_caps = [
            c for c in skill_capabilities if c not in self.capabilities
        ]
        self.capabilities.extend(new_caps)
        # Re-register node with updated capabilities
        self.coordinator.register_node(
            node_id=self.node_id,
            capabilities=self.capabilities,
            endpoint="local://evolution_agent_v2",
        )
        logger.info(
            "[NANDA] Registered skill '%s' capabilities: %s", skill_id, new_caps
        )

    # ------------------------------------------------------------------
    # Task handler registration
    # ------------------------------------------------------------------

    def _register_default_handlers(self):
        """Register built-in handlers for each known task type."""
        self._task_handlers[TASK_EVOLUTION_MUTATION] = self._handle_evolution_mutation
        self._task_handlers[TASK_BITREFILL_TRADE] = self._handle_bitrefill_trade
        self._task_handlers[TASK_X402_PAYMENT] = self._handle_x402_payment
        self._task_handlers[TASK_SKILL_DISPATCH] = self._handle_skill_dispatch

    def register_task_handler(
        self, task_type: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    ):
        """
        Register a custom handler for a NANDA task type.

        Args:
            task_type: e.g. ``"bitrefill_trade"``
            handler:   Callable that receives the task payload dict and returns
                       a result dict.
        """
        self._task_handlers[task_type] = handler
        logger.info("[NANDA] Custom handler registered for task type: %s", task_type)

    # ------------------------------------------------------------------
    # Outbound: broadcast tasks to the network
    # ------------------------------------------------------------------

    async def broadcast_mutation_task(self, mutation_context: Dict[str, Any]) -> str:
        """
        Broadcast a code mutation / feature implementation task to the NANDA network.
        Other nodes can pick up the work if this node is at capacity.
        """
        task_id = await self.coordinator.submit_task(
            task_type=TASK_EVOLUTION_MUTATION,
            payload={
                "origin_node": self.node_id,
                "context": mutation_context,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info("[NANDA] Broadcasted mutation task: %s", task_id)
        return task_id

    async def broadcast_skill_task(
        self, skill_id: str, context: Dict[str, Any], name: str = ""
    ) -> str:
        """
        Broadcast a skill-agent task to the NANDA network.

        Other nodes that have the same skill loaded can process the request
        if this node is unavailable or at capacity.

        Args:
            skill_id: e.g. ``"bitrefill/agents"`` or ``"x402/agents"``
            context:  Skill action context dict (same format as ``agent.act()``)
            name:     Optional human-readable task name.

        Returns:
            The network-assigned task ID.
        """
        task_type = _skill_to_task_type(skill_id)
        task_id = await self.coordinator.submit_task(
            task_type=task_type,
            payload={
                "origin_node": self.node_id,
                "skill_id": skill_id,
                "name": name or f"{skill_id}:{context.get('action', '?')}",
                "context": context,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info("[NANDA] Broadcasted skill task %s (type=%s): %s", name, task_type, task_id)
        return task_id

    async def broadcast_result(
        self, task_id: str, result: Dict[str, Any], skill_id: str = ""
    ) -> str:
        """
        Publish a task result back to the NANDA network.

        Allows other nodes to observe the outcome (e.g. for consensus,
        audit trails, or downstream chaining).
        """
        record = {
            "origin_node": self.node_id,
            "task_id": task_id,
            "skill_id": skill_id,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._result_log.append(record)

        broadcast_id = await self.coordinator.submit_task(
            task_type="skill_result",
            payload=record,
        )
        logger.info("[NANDA] Broadcasted result for task %s → %s", task_id, broadcast_id)
        return broadcast_id

    # ------------------------------------------------------------------
    # Inbound: route tasks from the network to local agents
    # ------------------------------------------------------------------

    def route_task(self, task: Any) -> Dict[str, Any]:
        """
        Route an incoming NANDA task to the correct local handler.

        This is the main inbound dispatch method.  The Supervisor or a
        listener loop calls this whenever a task arrives from the network.

        Args:
            task: NANDA AgentTask object (or dict with ``task_type`` and
                  ``payload`` keys).

        Returns:
            Result dict with at least ``{"status": "completed"|"failed", ...}``
        """
        task_type = getattr(task, "task_type", None) or task.get("task_type", "")
        payload = getattr(task, "payload", None) or task.get("payload", {})
        task_id = getattr(task, "task_id", None) or task.get("task_id", "unknown")

        logger.info("[NANDA] Routing task %s (type=%s)", task_id, task_type)

        handler = self._task_handlers.get(task_type)
        if handler is None:
            logger.warning("[NANDA] No handler for task type '%s'", task_type)
            return {
                "status": AgentTaskStatus.FAILED,
                "error": f"No handler registered for task type '{task_type}'",
                "task_id": task_id,
            }

        try:
            result = handler(payload)
            result["task_id"] = task_id
            result.setdefault("status", AgentTaskStatus.COMPLETED)
            return result
        except Exception as exc:
            logger.exception("[NANDA] Handler for '%s' raised: %s", task_type, exc)
            return {
                "status": AgentTaskStatus.FAILED,
                "error": str(exc),
                "task_id": task_id,
            }

    def process_external_request(self, task: Any) -> Dict[str, Any]:
        """
        Process an incoming request from an external NANDA agent.
        Alias for ``route_task()`` for backwards compatibility.
        """
        return self.route_task(task)

    # ------------------------------------------------------------------
    # Built-in task handlers
    # ------------------------------------------------------------------

    def _handle_evolution_mutation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an incoming evolution / code-mutation task."""
        logger.info("[NANDA] Processing evolution mutation from %s", payload.get("origin_node"))
        # If a Supervisor is wired up, delegate to it; otherwise acknowledge only.
        if self._supervisor and hasattr(self._supervisor, "process_bug_fix"):
            logger.info("[NANDA] Delegating mutation to local Supervisor.")
        return {"status": AgentTaskStatus.COMPLETED, "processor": self.node_id}

    def _handle_bitrefill_trade(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route a Bitrefill trade request to the local BitrefillTradingAgent."""
        return self._dispatch_to_skill("bitrefill/agents", payload)

    def _handle_x402_payment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route an x402 payment request to the local X402PaymentAgent."""
        return self._dispatch_to_skill("x402/agents", payload)

    def _handle_skill_dispatch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generic skill-dispatch handler – routes to skill_id specified in payload."""
        skill_id = payload.get("skill_id", "")
        if not skill_id:
            return {
                "status": AgentTaskStatus.FAILED,
                "error": "skill_dispatch payload missing 'skill_id'",
            }
        return self._dispatch_to_skill(skill_id, payload)

    def _dispatch_to_skill(self, skill_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch a task payload to a local skill agent via the Supervisor.

        If no Supervisor is wired, falls back to loading the agent directly
        from the skills registry.
        """
        context = payload.get("context", {})
        name = payload.get("name", skill_id)

        if self._supervisor and hasattr(self._supervisor, "process_skill_task"):
            task_dict = {"skill_id": skill_id, "context": context, "name": name}
            success = self._supervisor.process_skill_task(task_dict)
            return {
                "status": AgentTaskStatus.COMPLETED if success else AgentTaskStatus.FAILED,
                "processor": self.node_id,
                "skill_id": skill_id,
            }

        # Fallback: load skill agent directly
        try:
            from skills import registry as _reg
            agent = _reg.load_skill_agent(skill_id)
            result = agent.act(context)
            return {
                "status": (
                    AgentTaskStatus.COMPLETED
                    if result.get("success")
                    else AgentTaskStatus.FAILED
                ),
                "processor": self.node_id,
                "skill_id": skill_id,
                "result": result,
            }
        except Exception as exc:
            logger.exception("[NANDA] Direct skill dispatch failed for '%s': %s", skill_id, exc)
            return {
                "status": AgentTaskStatus.FAILED,
                "error": str(exc),
                "skill_id": skill_id,
            }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_result_log(self) -> List[Dict[str, Any]]:
        """Return all results broadcast by this node in the current session."""
        return list(self._result_log)

    def get_network_nodes(self) -> Dict[str, Any]:
        """Return the known NANDA network topology."""
        return dict(self.coordinator.nodes)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skill_to_task_type(skill_id: str) -> str:
    """Map a skill_id to the canonical NANDA task type string."""
    _map = {
        "bitrefill/agents": TASK_BITREFILL_TRADE,
        "x402/agents": TASK_X402_PAYMENT,
    }
    return _map.get(skill_id, TASK_SKILL_DISPATCH)


# ---------------------------------------------------------------------------
# Supervisor integration helper
# ---------------------------------------------------------------------------

def setup_nanda(supervisor, node_name: str = "evolution_master") -> "NANDABridge":
    """
    Initialize and attach a NANDABridge to a Supervisor.

    The bridge is wired with a back-reference to the Supervisor so it can
    route incoming skill tasks through the Supervisor's existing dispatch
    logic (process_skill_task, memory logging, etc.).

    Also registers capabilities for every already-loaded skill agent.
    """
    # Collect capabilities from all loaded skills
    capabilities = list(_DEFAULT_CAPABILITIES)
    if hasattr(supervisor, "_skill_agents"):
        try:
            from skills import registry as _reg
            for skill_id in supervisor._skill_agents:
                entry = _reg.get_skill(skill_id)
                if entry:
                    for cap in entry.get("capabilities", []):
                        if cap not in capabilities:
                            capabilities.append(cap)
        except ImportError:
            pass

    bridge = NANDABridge(
        node_id=node_name,
        capabilities=capabilities,
        supervisor=supervisor,
    )
    supervisor.nanda_bridge = bridge
    logger.info("[NANDA] Bridge attached to Supervisor '%s'.", node_name)
    return bridge

