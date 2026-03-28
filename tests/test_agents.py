# tests/test_agents.py
# Tests for evolution/agents.py

import os
import pytest


# ── Ensure the module can be imported even without an API key ────────────────

def test_import_without_api_key(monkeypatch):
    """Regression: importing agents must succeed when OPENAI_API_KEY is unset."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import importlib
    import sys

    # Remove any cached module so it re-executes the module-level client init
    for mod in list(sys.modules.keys()):
        if mod.startswith("evolution"):
            del sys.modules[mod]

    # This must not raise
    from evolution.agents import ObserverAgent  # noqa: F401


def test_import_with_api_key(monkeypatch):
    """Module imports successfully when OPENAI_API_KEY is provided."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")

    import importlib
    import sys

    for mod in list(sys.modules.keys()):
        if mod.startswith("evolution"):
            del sys.modules[mod]

    from evolution.agents import ObserverAgent, ArchitectAgent, AuditorAgent, PlannerAgent  # noqa: F401


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def set_dummy_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


@pytest.fixture()
def observer():
    from evolution.agents import ObserverAgent
    return ObserverAgent()


@pytest.fixture()
def auditor():
    from evolution.agents import AuditorAgent
    return AuditorAgent()


# ── ObserverAgent ─────────────────────────────────────────────────────────────

class TestObserverAgent:
    def test_missing_log_returns_none(self, observer):
        result = observer.act("/tmp/nonexistent_log_xyz.log")
        assert result is None

    def test_empty_log_returns_none(self, observer, tmp_path):
        log = tmp_path / "empty.log"
        log.write_text("")
        assert observer.act(str(log)) is None

    def test_detects_zero_division_error(self, observer, tmp_path):
        log = tmp_path / "err.log"
        log.write_text("CRITICAL ERROR: ZeroDivisionError: division by zero\nTraceback...\n")
        result = observer.act(str(log))
        assert result is not None
        assert result["type"] in ("ZeroDivisionError", "Error", "CRITICAL")

    def test_detects_critical_keyword(self, observer, tmp_path):
        log = tmp_path / "crit.log"
        log.write_text("CRITICAL: something went wrong\n")
        result = observer.act(str(log))
        assert result is not None
        assert result["type"] == "CRITICAL"

    def test_detects_exception_keyword(self, observer, tmp_path):
        log = tmp_path / "exc.log"
        log.write_text("Exception occurred during processing\n")
        result = observer.act(str(log))
        assert result is not None

    def test_result_has_required_keys(self, observer, tmp_path):
        log = tmp_path / "err.log"
        log.write_text("CRITICAL ERROR: boom\n")
        result = observer.act(str(log))
        assert "type" in result
        assert "log_excerpt" in result
        assert "timestamp" in result

    def test_no_error_keywords_returns_anomaly_or_none(self, observer, tmp_path):
        log = tmp_path / "info.log"
        log.write_text("INFO: all systems operational\n")
        # Does not match any error keyword -> result is None (type stays 'unknown')
        result = observer.act(str(log))
        # Either None or an anomaly record — not a false positive error
        if result is not None:
            assert result["type"] == "anomaly"


# ── AuditorAgent ──────────────────────────────────────────────────────────────

class TestAuditorAgent:
    def test_valid_code_accepted(self, auditor):
        assert auditor.act("def foo():\n    return 1\n") is True

    def test_empty_string_rejected(self, auditor):
        assert auditor.act("") is False

    def test_none_rejected(self, auditor):
        assert auditor.act(None) is False

    def test_whitespace_only_rejected(self, auditor):
        assert auditor.act("   \n\t  ") is False

    def test_syntax_error_rejected(self, auditor):
        assert auditor.act("def foo( return 1") is False

    def test_multiline_valid_code(self, auditor):
        code = (
            "import os\n"
            "def hello(name):\n"
            "    print(f'Hello {name}')\n"
            "if __name__ == '__main__':\n"
            "    hello('world')\n"
        )
        assert auditor.act(code) is True


# ── RuntimeContextBridge ──────────────────────────────────────────────────────

class TestRuntimeContextBridge:
    def test_known_scope_returns_context(self):
        from evolution.agents import RuntimeContextBridge

        bridge = RuntimeContextBridge()

        def sample_func(x):
            return x * 2

        result = bridge.execute(scope_name="sample_func")
        assert isinstance(result, dict)
        assert "current_scope" in result
        assert "source_snapshot" in result

    def test_unknown_scope_returns_error(self):
        from evolution.agents import RuntimeContextBridge

        bridge = RuntimeContextBridge()
        result = bridge.execute(scope_name="definitely_not_here_xyz")
        assert "error" in result
