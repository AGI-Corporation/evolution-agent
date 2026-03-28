# tests/test_nanda_bridge.py
# Tests for evolution/nanda_bridge.py

import asyncio
import pytest
from evolution.nanda_bridge import NANDABridge, setup_nanda


class TestNANDABridge:
    def test_initializes_with_node_id(self):
        bridge = NANDABridge("test_node_001")
        assert bridge.node_id == "test_node_001"

    def test_default_capabilities(self):
        bridge = NANDABridge("node_x")
        assert "code_mutation" in bridge.capabilities

    def test_custom_capabilities(self):
        bridge = NANDABridge("node_y", capabilities=["analysis", "reporting"])
        assert bridge.capabilities == ["analysis", "reporting"]

    def test_broadcast_returns_task_id(self):
        bridge = NANDABridge("node_z")

        async def run():
            task_id = await bridge.broadcast_mutation_task({"target": "main_app.py"})
            return task_id

        task_id = asyncio.run(run())
        assert task_id is not None
        assert isinstance(task_id, str)

    def test_process_external_request_accepted(self):
        bridge = NANDABridge("node_ext")

        class FakeTask:
            task_id = "ext-task-001"

        result = bridge.process_external_request(FakeTask())
        assert result["status"] == "accepted"
        assert result["processor"] == "node_ext"

    def test_process_request_without_task_id(self):
        bridge = NANDABridge("node_ext2")

        class NoIdTask:
            pass

        result = bridge.process_external_request(NoIdTask())
        assert "status" in result


class TestSetupNanda:
    def test_attaches_bridge_to_supervisor(self):
        class FakeSupervisor:
            nanda_bridge = None

        sup = FakeSupervisor()
        bridge = setup_nanda(sup, node_name="test_master")
        assert isinstance(bridge, NANDABridge)
        assert sup.nanda_bridge is bridge
        assert bridge.node_id == "test_master"
