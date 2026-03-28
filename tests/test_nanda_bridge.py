# tests/test_nanda_bridge.py
# Tests for evolution/nanda_bridge.py

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from evolution.nanda_bridge import NANDABridge, setup_nanda


# ---------------------------------------------------------------------------
# NANDABridge.__init__
# ---------------------------------------------------------------------------

class TestNANDABridgeInit:
    def test_node_id_stored(self):
        bridge = NANDABridge(node_id="test_node")
        assert bridge.node_id == "test_node"

    def test_default_capabilities(self):
        bridge = NANDABridge(node_id="n1")
        assert isinstance(bridge.capabilities, list)
        assert len(bridge.capabilities) > 0

    def test_custom_capabilities(self):
        caps = ["code_mutation", "reporting"]
        bridge = NANDABridge(node_id="n1", capabilities=caps)
        assert bridge.capabilities == caps

    def test_coordinator_initialized(self):
        bridge = NANDABridge(node_id="n1")
        assert bridge.coordinator is not None


# ---------------------------------------------------------------------------
# broadcast_mutation_task
# ---------------------------------------------------------------------------

class TestBroadcastMutationTask:
    def test_returns_task_id(self):
        bridge = NANDABridge(node_id="test_node")
        context = {"mutation_type": "code_fix", "target": "main_app.py"}

        result = asyncio.get_event_loop().run_until_complete(
            bridge.broadcast_mutation_task(context)
        )
        assert result is not None
        assert isinstance(result, str)

    def test_task_id_contains_timestamp(self):
        bridge = NANDABridge(node_id="node1")
        context = {}
        task_id = asyncio.get_event_loop().run_until_complete(
            bridge.broadcast_mutation_task(context)
        )
        # The mock task_id is "task_<timestamp>"
        assert task_id.startswith("task_")


# ---------------------------------------------------------------------------
# process_external_request
# ---------------------------------------------------------------------------

class TestProcessExternalRequest:
    def test_returns_accepted_status(self):
        bridge = NANDABridge(node_id="test_node")
        mock_task = MagicMock()
        mock_task.task_id = "incoming_task_123"
        result = bridge.process_external_request(mock_task)
        assert result["status"] == "accepted"

    def test_returns_processor_node(self):
        bridge = NANDABridge(node_id="my_node")
        mock_task = MagicMock()
        result = bridge.process_external_request(mock_task)
        assert result["processor"] == "my_node"

    def test_handles_task_without_task_id(self):
        bridge = NANDABridge(node_id="node1")
        # Task without task_id attribute (uses getattr default)
        result = bridge.process_external_request(object())
        assert result["status"] == "accepted"


# ---------------------------------------------------------------------------
# setup_nanda helper
# ---------------------------------------------------------------------------

class TestSetupNanda:
    def test_attaches_bridge_to_supervisor(self):
        mock_supervisor = MagicMock()
        bridge = setup_nanda(mock_supervisor, node_name="evo_master")
        assert isinstance(bridge, NANDABridge)
        assert mock_supervisor.nanda_bridge is bridge

    def test_uses_custom_node_name(self):
        mock_supervisor = MagicMock()
        bridge = setup_nanda(mock_supervisor, node_name="custom_node")
        assert bridge.node_id == "custom_node"

    def test_default_node_name(self):
        mock_supervisor = MagicMock()
        bridge = setup_nanda(mock_supervisor)
        assert bridge.node_id == "evolution_master"
