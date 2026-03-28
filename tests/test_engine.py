# tests/test_engine.py
# Tests for evolution/engine.py

import json
import os
import pytest


@pytest.fixture(autouse=True)
def set_dummy_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


@pytest.fixture()
def project_root(tmp_path):
    os.makedirs(tmp_path / "logs", exist_ok=True)
    os.makedirs(tmp_path / "evolution", exist_ok=True)
    # Provide a minimal main_app.py
    (tmp_path / "main_app.py").write_text("def main(): pass\n")
    return str(tmp_path)


@pytest.fixture()
def engine(project_root):
    from evolution.engine import EvolutionEngine
    return EvolutionEngine(project_root)


class TestEvolutionEngineInit:
    def test_memory_file_created(self, engine, project_root):
        assert os.path.exists(engine.memory_file)
        with open(engine.memory_file) as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_read_source_returns_code(self, engine):
        src = engine.read_source()
        assert src is not None
        assert "def main" in src

    def test_read_source_missing_file(self, engine):
        engine.target_file = "/tmp/nonexistent_main_xyz.py"
        result = engine.read_source()
        assert result is None


class TestEvolutionEngineHealthy:
    def test_healthy_system_returns_false(self, engine, project_root):
        # Empty log = no issue detected
        log_path = os.path.join(project_root, "logs", "system.log")
        open(log_path, "w").close()
        result = engine.run_evolution_cycle()
        assert result is False

    def test_clear_log(self, engine, project_root):
        log_path = os.path.join(project_root, "logs", "system.log")
        with open(log_path, "w") as f:
            f.write("some content\n")
        engine.clear_log()
        assert open(log_path).read() == ""


class TestEvolutionEngineMemory:
    def test_save_memory_appends_entry(self, engine):
        issue = {"type": "ZeroDivisionError"}
        engine.save_memory(issue, "proposed patch preview")
        with open(engine.memory_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["issue_type"] == "ZeroDivisionError"

    def test_save_memory_truncates_long_patch(self, engine):
        issue = {"type": "NameError"}
        long_patch = "x" * 500
        engine.save_memory(issue, long_patch)
        with open(engine.memory_file) as f:
            data = json.load(f)
        assert len(data[0]["fix_preview"]) <= 203  # 200 + "..."
