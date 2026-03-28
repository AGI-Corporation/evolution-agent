# tests/test_engine.py
# Tests for evolution/engine.py

import json
import os
import pytest
from unittest.mock import MagicMock, patch, call
from evolution.engine import EvolutionEngine


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal project structure."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "evolution").mkdir()
    (tmp_path / "logs" / "system.log").write_text("")
    (tmp_path / "main_app.py").write_text("def main(): pass\n")
    return tmp_path


@pytest.fixture
def engine(tmp_project):
    with patch("evolution.engine.ObserverAgent"), \
         patch("evolution.engine.ArchitectAgent"), \
         patch("evolution.engine.AuditorAgent"), \
         patch("evolution.engine.Sandbox"):
        eng = EvolutionEngine(str(tmp_project))
    return eng


# ---------------------------------------------------------------------------
# __init__ and memory
# ---------------------------------------------------------------------------

class TestEvolutionEngineInit:
    def test_memory_file_created_if_absent(self, tmp_project):
        with patch("evolution.engine.ObserverAgent"), \
             patch("evolution.engine.ArchitectAgent"), \
             patch("evolution.engine.AuditorAgent"), \
             patch("evolution.engine.Sandbox"):
            eng = EvolutionEngine(str(tmp_project))
        assert os.path.exists(eng.memory_file)
        with open(eng.memory_file) as f:
            data = json.load(f)
        assert data == []

    def test_memory_file_not_overwritten_if_exists(self, tmp_project):
        memory_path = tmp_project / "evolution" / "memory.json"
        memory_path.write_text(json.dumps([{"existing": "entry"}]))
        with patch("evolution.engine.ObserverAgent"), \
             patch("evolution.engine.ArchitectAgent"), \
             patch("evolution.engine.AuditorAgent"), \
             patch("evolution.engine.Sandbox"):
            eng = EvolutionEngine(str(tmp_project))
        with open(eng.memory_file) as f:
            data = json.load(f)
        assert data[0]["existing"] == "entry"

    def test_paths_set_correctly(self, tmp_project):
        with patch("evolution.engine.ObserverAgent"), \
             patch("evolution.engine.ArchitectAgent"), \
             patch("evolution.engine.AuditorAgent"), \
             patch("evolution.engine.Sandbox"):
            eng = EvolutionEngine(str(tmp_project))
        assert eng.project_root == str(tmp_project)
        assert "system.log" in eng.log_path
        assert "main_app.py" in eng.target_file


# ---------------------------------------------------------------------------
# save_memory
# ---------------------------------------------------------------------------

class TestSaveMemory:
    def test_save_memory_appends_entry(self, engine):
        issue = {"type": "Error"}
        engine.save_memory(issue, "some patch code here")
        with open(engine.memory_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["issue_type"] == "Error"

    def test_save_memory_truncates_long_preview(self, engine):
        issue = {"type": "Error"}
        long_patch = "x" * 500
        engine.save_memory(issue, long_patch)
        with open(engine.memory_file) as f:
            data = json.load(f)
        assert data[0]["fix_preview"].endswith("...")
        assert len(data[0]["fix_preview"]) <= 203  # 200 + len("...")

    def test_save_memory_short_preview_not_truncated(self, engine):
        issue = {"type": "Error"}
        short_patch = "fix code"
        engine.save_memory(issue, short_patch)
        with open(engine.memory_file) as f:
            data = json.load(f)
        assert data[0]["fix_preview"] == "fix code"


# ---------------------------------------------------------------------------
# read_source
# ---------------------------------------------------------------------------

class TestReadSource:
    def test_read_existing_file(self, engine, tmp_project):
        content = "def main(): pass\n"
        (tmp_project / "main_app.py").write_text(content)
        result = engine.read_source()
        assert result == content

    def test_read_missing_file_returns_none(self, engine):
        engine.target_file = "/nonexistent/main_app.py"
        result = engine.read_source()
        assert result is None


# ---------------------------------------------------------------------------
# clear_log
# ---------------------------------------------------------------------------

class TestClearLog:
    def test_clear_log_empties_file(self, engine, tmp_project):
        (tmp_project / "logs" / "system.log").write_text("old log data")
        engine.clear_log()
        content = (tmp_project / "logs" / "system.log").read_text()
        assert content == ""

    def test_clear_log_missing_file_does_not_raise(self, engine):
        engine.log_path = "/nonexistent/path/system.log"
        # Should not raise, just print an error
        engine.clear_log()


# ---------------------------------------------------------------------------
# run_evolution_cycle
# ---------------------------------------------------------------------------

class TestRunEvolutionCycle:
    def test_healthy_system_returns_false(self, engine):
        engine.observer.act.return_value = None
        result = engine.run_evolution_cycle()
        assert result is False

    def test_no_source_returns_false(self, engine):
        engine.observer.act.return_value = {"type": "Error", "log_excerpt": "err"}
        engine.target_file = "/nonexistent/main_app.py"
        result = engine.run_evolution_cycle()
        assert result is False

    def test_architect_fails_returns_false(self, engine):
        engine.observer.act.return_value = {"type": "Error", "log_excerpt": "err"}
        engine.architect.act.return_value = None
        result = engine.run_evolution_cycle()
        assert result is False

    def test_auditor_rejects_returns_false(self, engine):
        engine.observer.act.return_value = {"type": "Error", "log_excerpt": "err"}
        engine.architect.act.return_value = "def fixed(): pass"
        engine.auditor.act.return_value = False
        result = engine.run_evolution_cycle()
        assert result is False

    def test_sandbox_fails_returns_false(self, engine):
        engine.observer.act.return_value = {"type": "Error", "log_excerpt": "err"}
        engine.architect.act.return_value = "def fixed(): pass"
        engine.auditor.act.return_value = True
        engine.sandbox.verify_and_apply.return_value = False
        result = engine.run_evolution_cycle()
        assert result is False

    def test_full_success_returns_true(self, engine):
        engine.observer.act.return_value = {"type": "Error", "log_excerpt": "err"}
        engine.architect.act.return_value = "def fixed(): pass"
        engine.auditor.act.return_value = True
        engine.sandbox.verify_and_apply.return_value = True
        result = engine.run_evolution_cycle()
        assert result is True

    def test_full_success_saves_memory(self, engine):
        engine.observer.act.return_value = {"type": "ZeroDivisionError", "log_excerpt": "err"}
        engine.architect.act.return_value = "def fixed(): pass"
        engine.auditor.act.return_value = True
        engine.sandbox.verify_and_apply.return_value = True
        engine.run_evolution_cycle()
        with open(engine.memory_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["issue_type"] == "ZeroDivisionError"

    def test_full_success_clears_log(self, engine, tmp_project):
        (tmp_project / "logs" / "system.log").write_text("some error")
        engine.observer.act.return_value = {"type": "Error", "log_excerpt": "err"}
        engine.architect.act.return_value = "def fixed(): pass"
        engine.auditor.act.return_value = True
        engine.sandbox.verify_and_apply.return_value = True
        engine.run_evolution_cycle()
        assert (tmp_project / "logs" / "system.log").read_text() == ""


# ---------------------------------------------------------------------------
# run (loop)
# ---------------------------------------------------------------------------

class TestRun:
    def test_run_stops_after_max_cycles(self, engine):
        engine.observer.act.return_value = None  # healthy system
        with patch("time.sleep"):
            engine.run(interval=0, max_cycles=3)
        assert engine.observer.act.call_count == 3

    def test_run_sleeps_between_cycles(self, engine):
        engine.observer.act.return_value = None
        with patch("time.sleep") as mock_sleep:
            engine.run(interval=5, max_cycles=2)
        # sleep is called after each cycle EXCEPT the last (loop breaks before sleeping)
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(5)
