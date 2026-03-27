# tests/test_engine.py

import json
import os
import pytest
from unittest.mock import patch, MagicMock, call
from evolution.engine import EvolutionEngine


def _make_engine(tmp_path):
    """Create an EvolutionEngine backed by a real temporary directory."""
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "logs" / "system.log").write_text("")
    (tmp_path / "evolution").mkdir(parents=True, exist_ok=True)
    (tmp_path / "main_app.py").write_text("def main(): pass\n")
    engine = EvolutionEngine(str(tmp_path))
    return engine


class TestEvolutionEngineInit:
    def test_init_creates_memory_file(self, tmp_path):
        engine = _make_engine(tmp_path)
        memory_file = tmp_path / "evolution" / "memory.json"
        assert memory_file.exists()
        data = json.loads(memory_file.read_text())
        assert data == []

    def test_init_does_not_overwrite_existing_memory(self, tmp_path):
        memory_dir = tmp_path / "evolution"
        memory_dir.mkdir(parents=True, exist_ok=True)
        existing = [{"type": "bug_fix"}]
        (memory_dir / "memory.json").write_text(json.dumps(existing))
        engine = _make_engine(tmp_path)
        data = json.loads((memory_dir / "memory.json").read_text())
        assert data == existing

    def test_target_file_path_set_correctly(self, tmp_path):
        engine = _make_engine(tmp_path)
        assert engine.target_file == str(tmp_path / "main_app.py")

    def test_log_path_set_correctly(self, tmp_path):
        engine = _make_engine(tmp_path)
        assert engine.log_path == str(tmp_path / "logs" / "system.log")


class TestEvolutionEngineSaveMemory:
    def test_save_memory_appends_entry(self, tmp_path):
        engine = _make_engine(tmp_path)
        issue = {"type": "ZeroDivisionError"}
        engine.save_memory(issue, "patch code here")
        data = json.loads((tmp_path / "evolution" / "memory.json").read_text())
        assert len(data) == 1
        assert data[0]["issue_type"] == "ZeroDivisionError"

    def test_save_memory_truncates_long_patch(self, tmp_path):
        engine = _make_engine(tmp_path)
        long_patch = "x" * 500
        engine.save_memory({"type": "Error"}, long_patch)
        data = json.loads((tmp_path / "evolution" / "memory.json").read_text())
        assert data[0]["fix_preview"].endswith("...")
        assert len(data[0]["fix_preview"]) <= 203  # 200 chars + "..."

    def test_save_memory_short_patch_not_truncated(self, tmp_path):
        engine = _make_engine(tmp_path)
        short_patch = "fix"
        engine.save_memory({"type": "Error"}, short_patch)
        data = json.loads((tmp_path / "evolution" / "memory.json").read_text())
        assert data[0]["fix_preview"] == "fix"

    def test_save_memory_multiple_entries(self, tmp_path):
        engine = _make_engine(tmp_path)
        engine.save_memory({"type": "Error"}, "patch1")
        engine.save_memory({"type": "TypeError"}, "patch2")
        data = json.loads((tmp_path / "evolution" / "memory.json").read_text())
        assert len(data) == 2

    def test_save_memory_includes_timestamp(self, tmp_path):
        engine = _make_engine(tmp_path)
        engine.save_memory({"type": "Error"}, "patch")
        data = json.loads((tmp_path / "evolution" / "memory.json").read_text())
        assert "timestamp" in data[0]


class TestEvolutionEngineReadSource:
    def test_read_existing_file(self, tmp_path):
        engine = _make_engine(tmp_path)
        content = engine.read_source()
        assert content == "def main(): pass\n"

    def test_read_missing_file_returns_none(self, tmp_path):
        engine = _make_engine(tmp_path)
        engine.target_file = str(tmp_path / "nonexistent.py")
        assert engine.read_source() is None


class TestEvolutionEngineClearLog:
    def test_clear_log_empties_file(self, tmp_path):
        engine = _make_engine(tmp_path)
        log_file = tmp_path / "logs" / "system.log"
        log_file.write_text("Error: something went wrong\n")
        engine.clear_log()
        assert log_file.read_text() == ""


class TestEvolutionEngineRunCycle:
    def test_no_issue_returns_false(self, tmp_path):
        engine = _make_engine(tmp_path)
        with patch.object(engine.observer, "act", return_value=None):
            result = engine.run_evolution_cycle()
        assert result is False

    def test_missing_source_returns_false(self, tmp_path):
        engine = _make_engine(tmp_path)
        issue = {"type": "Error", "log_excerpt": "err"}
        engine.target_file = str(tmp_path / "missing.py")
        with patch.object(engine.observer, "act", return_value=issue):
            result = engine.run_evolution_cycle()
        assert result is False

    def test_architect_returns_none_returns_false(self, tmp_path):
        engine = _make_engine(tmp_path)
        issue = {"type": "Error", "log_excerpt": "err"}
        with (
            patch.object(engine.observer, "act", return_value=issue),
            patch.object(engine.architect, "act", return_value=None),
        ):
            result = engine.run_evolution_cycle()
        assert result is False

    def test_auditor_rejects_returns_false(self, tmp_path):
        engine = _make_engine(tmp_path)
        issue = {"type": "Error", "log_excerpt": "err"}
        with (
            patch.object(engine.observer, "act", return_value=issue),
            patch.object(engine.architect, "act", return_value="patch"),
            patch.object(engine.auditor, "act", return_value=False),
        ):
            result = engine.run_evolution_cycle()
        assert result is False

    def test_sandbox_failure_returns_false(self, tmp_path):
        engine = _make_engine(tmp_path)
        issue = {"type": "Error", "log_excerpt": "err"}
        with (
            patch.object(engine.observer, "act", return_value=issue),
            patch.object(engine.architect, "act", return_value="patch"),
            patch.object(engine.auditor, "act", return_value=True),
            patch.object(engine.sandbox, "verify_and_apply", return_value=False),
        ):
            result = engine.run_evolution_cycle()
        assert result is False

    def test_full_success_returns_true_and_saves_memory(self, tmp_path):
        engine = _make_engine(tmp_path)
        issue = {"type": "ZeroDivisionError", "log_excerpt": "div by zero"}
        patch_code = "def main(): pass  # fixed\n"
        with (
            patch.object(engine.observer, "act", return_value=issue),
            patch.object(engine.architect, "act", return_value=patch_code),
            patch.object(engine.auditor, "act", return_value=True),
            patch.object(engine.sandbox, "verify_and_apply", return_value=True),
        ):
            result = engine.run_evolution_cycle()
        assert result is True
        data = json.loads((tmp_path / "evolution" / "memory.json").read_text())
        assert len(data) == 1
        assert data[0]["issue_type"] == "ZeroDivisionError"

    def test_full_success_clears_log(self, tmp_path):
        engine = _make_engine(tmp_path)
        log_file = tmp_path / "logs" / "system.log"
        log_file.write_text("ZeroDivisionError: division by zero\n")
        issue = {"type": "ZeroDivisionError", "log_excerpt": "div by zero"}
        with (
            patch.object(engine.observer, "act", return_value=issue),
            patch.object(engine.architect, "act", return_value="def f(): pass\n"),
            patch.object(engine.auditor, "act", return_value=True),
            patch.object(engine.sandbox, "verify_and_apply", return_value=True),
        ):
            engine.run_evolution_cycle()
        assert log_file.read_text() == ""


class TestEvolutionEngineRun:
    def test_run_stops_after_max_cycles(self, tmp_path):
        engine = _make_engine(tmp_path)
        call_count = []

        def fake_cycle():
            call_count.append(1)
            return False

        with (
            patch.object(engine, "run_evolution_cycle", side_effect=fake_cycle),
            patch("time.sleep"),
        ):
            engine.run(interval=0, max_cycles=3)

        assert len(call_count) == 3

    def test_run_sleeps_between_cycles(self, tmp_path):
        engine = _make_engine(tmp_path)
        with (
            patch.object(engine, "run_evolution_cycle", return_value=False),
            patch("time.sleep") as mock_sleep,
        ):
            engine.run(interval=15, max_cycles=2)
        # sleep is called after each cycle except the last one
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(15)
