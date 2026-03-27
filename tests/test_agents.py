# tests/test_agents.py

import json
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# ObserverAgent
# ---------------------------------------------------------------------------

class TestObserverAgent:
    def _make_agent(self):
        from evolution.agents import ObserverAgent
        return ObserverAgent()

    def test_name(self):
        agent = self._make_agent()
        assert agent.name == "Observer"

    def test_scan_logs_returns_file_content(self, tmp_path):
        log_file = tmp_path / "system.log"
        log_file.write_text("line1\nline2\nline3\n")
        agent = self._make_agent()
        result = agent.scan_logs(str(log_file))
        assert "line1" in result
        assert "line3" in result

    def test_scan_logs_missing_file_returns_empty(self):
        agent = self._make_agent()
        result = agent.scan_logs("/nonexistent/path/log.txt")
        assert result == ""

    def test_scan_logs_returns_at_most_last_50_lines(self, tmp_path):
        lines = [f"line{i}\n" for i in range(100)]
        log_file = tmp_path / "system.log"
        log_file.write_text("".join(lines))
        agent = self._make_agent()
        result = agent.scan_logs(str(log_file))
        assert "line99" in result
        assert "line0\n" not in result

    def test_act_empty_log_returns_none(self, tmp_path):
        log_file = tmp_path / "system.log"
        log_file.write_text("")
        agent = self._make_agent()
        assert agent.act(str(log_file)) is None

    def test_act_whitespace_only_log_returns_none(self, tmp_path):
        log_file = tmp_path / "system.log"
        log_file.write_text("   \n   \n")
        agent = self._make_agent()
        assert agent.act(str(log_file)) is None

    def test_act_missing_log_returns_none(self, tmp_path):
        agent = self._make_agent()
        assert agent.act(str(tmp_path / "nonexistent.log")) is None

    @pytest.mark.parametrize("keyword,log_line", [
        # Keywords that win outright (not shadowed by an earlier entry)
        ("Error", "An Error occurred in the system\n"),
        ("Exception", "An Exception was raised here\n"),
        ("Traceback", "Traceback (most recent call last):\n"),
        ("CRITICAL", "CRITICAL: system failure detected\n"),
        ("FATAL", "FATAL: process terminated\n"),
        # Compound error names all contain "Error" as a substring,
        # so "Error" (which is earlier in the list) will be matched first.
        # The expected type is therefore "Error", not the full name.
        ("Error", "ZeroDivisionError: division by zero\n"),
        ("Error", "NameError: name 'x' is not defined\n"),
        ("Error", "TypeError: unsupported operand types\n"),
        ("Error", "AttributeError: 'NoneType' object has no attribute 'x'\n"),
    ])
    def test_act_detects_error_keywords(self, tmp_path, keyword, log_line):
        log_file = tmp_path / "system.log"
        log_file.write_text(log_line)
        agent = self._make_agent()
        result = agent.act(str(log_file))
        assert result is not None
        assert result["type"] == keyword

    def test_act_anomaly_when_no_keyword_matches(self, tmp_path):
        log_file = tmp_path / "system.log"
        log_file.write_text("Unusual output with no recognizable keyword\n")
        agent = self._make_agent()
        result = agent.act(str(log_file))
        assert result is not None
        assert result["type"] == "anomaly"

    def test_act_returns_required_fields(self, tmp_path):
        log_file = tmp_path / "system.log"
        log_file.write_text("CRITICAL: system failure detected\n")
        agent = self._make_agent()
        result = agent.act(str(log_file))
        assert result is not None
        assert "type" in result
        assert "log_excerpt" in result
        assert "timestamp" in result

    def test_act_first_keyword_wins(self, tmp_path):
        # "Error" appears before "Exception" in the keyword list, so a log
        # containing both results in type "Error".
        log_file = tmp_path / "system.log"
        log_file.write_text("Exception: An Error happened here\n")
        agent = self._make_agent()
        result = agent.act(str(log_file))
        assert result is not None
        assert result["type"] == "Error"


# ---------------------------------------------------------------------------
# ArchitectAgent
# ---------------------------------------------------------------------------

class TestArchitectAgent:
    def _make_agent(self):
        from evolution.agents import ArchitectAgent
        return ArchitectAgent()

    def test_name(self):
        assert self._make_agent().name == "Architect"

    def test_act_no_client_returns_none(self):
        with patch("evolution.agents.client", None):
            agent = self._make_agent()
            result = agent.act(
                {"type": "ZeroDivisionError", "log_excerpt": "division by zero"},
                "def foo(): pass",
            )
        assert result is None

    def test_act_returns_llm_response(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = (
            "def foo():\n    return 1\n"
        )
        with patch("evolution.agents.client", mock_client):
            agent = self._make_agent()
            result = agent.act(
                {"type": "ZeroDivisionError", "log_excerpt": "division by zero"},
                "def foo(): pass",
            )
        assert result == "def foo():\n    return 1\n"

    def test_act_strips_markdown_fences(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = (
            "```python\ndef fixed(): pass\n```"
        )
        with patch("evolution.agents.client", mock_client):
            agent = self._make_agent()
            result = agent.act(
                {"type": "Error", "log_excerpt": "err"},
                "def broken(): pass",
            )
        assert result == "def fixed(): pass"

    def test_act_passes_issue_type_in_prompt(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = "code"
        with patch("evolution.agents.client", mock_client):
            agent = self._make_agent()
            agent.act(
                {"type": "NameError", "log_excerpt": "name 'x' is not defined"},
                "x = y",
            )
        call_args = mock_client.chat.completions.create.call_args
        prompt = call_args[1]["messages"][0]["content"]
        assert "NameError" in prompt or "name 'x' is not defined" in prompt


# ---------------------------------------------------------------------------
# AuditorAgent
# ---------------------------------------------------------------------------

class TestAuditorAgent:
    def _make_agent(self):
        from evolution.agents import AuditorAgent
        return AuditorAgent()

    def test_name(self):
        assert self._make_agent().name == "Auditor"

    def test_act_none_returns_false(self):
        assert self._make_agent().act(None) is False

    def test_act_empty_string_returns_false(self):
        assert self._make_agent().act("") is False

    def test_act_whitespace_returns_false(self):
        assert self._make_agent().act("   ") is False

    def test_act_valid_python_returns_true(self):
        valid_code = "def foo(x):\n    return x * 2\n"
        assert self._make_agent().act(valid_code) is True

    def test_act_syntax_error_returns_false(self):
        bad_code = "def foo(\n    return 1\n"
        assert self._make_agent().act(bad_code) is False

    def test_act_multiline_valid_code(self):
        code = (
            "import os\n"
            "class Foo:\n"
            "    def bar(self): return 42\n"
        )
        assert self._make_agent().act(code) is True


# ---------------------------------------------------------------------------
# PlannerAgent
# ---------------------------------------------------------------------------

class TestPlannerAgent:
    def _make_agent(self):
        from evolution.agents import PlannerAgent
        return PlannerAgent()

    def test_name(self):
        assert self._make_agent().name == "Planner"

    def test_implement_feature_no_client_returns_none(self):
        with patch("evolution.agents.client", None):
            agent = self._make_agent()
            result = agent.implement_feature(
                {"name": "feature", "description": "do stuff"}, {}
            )
        assert result is None

    def test_implement_feature_valid_json_response(self):
        payload = {
            "plan": "add a helper function",
            "files_to_update": {"main_app.py": "def helper(): pass"},
            "new_files": {},
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = (
            json.dumps(payload)
        )
        with patch("evolution.agents.client", mock_client):
            agent = self._make_agent()
            result = agent.implement_feature(
                {"name": "helper", "description": "add helper"},
                {"main_app.py": "# existing"},
            )
        assert result == payload

    def test_implement_feature_strips_markdown_from_json(self):
        payload = {"plan": "x", "files_to_update": {}, "new_files": {}}
        raw = "```json\n" + json.dumps(payload) + "\n```"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = raw
        with patch("evolution.agents.client", mock_client):
            agent = self._make_agent()
            result = agent.implement_feature(
                {"name": "x", "description": "y"}, {}
            )
        assert result == payload

    def test_implement_feature_invalid_json_returns_none(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = (
            "this is not json at all"
        )
        with patch("evolution.agents.client", mock_client):
            agent = self._make_agent()
            result = agent.implement_feature(
                {"name": "x", "description": "y"}, {}
            )
        assert result is None

    def test_act_delegates_to_implement_feature(self):
        agent = self._make_agent()
        req = {"name": "feat", "description": "desc"}
        files = {"main_app.py": "code"}
        with patch.object(agent, "implement_feature", return_value={"plan": "ok"}) as mock_impl:
            result = agent.act({"requirement": req, "current_files": files})
        mock_impl.assert_called_once_with(req, files)
        assert result == {"plan": "ok"}


# ---------------------------------------------------------------------------
# RuntimeContextBridge
# ---------------------------------------------------------------------------

class TestRuntimeContextBridge:
    def _make_bridge(self):
        from evolution.agents import RuntimeContextBridge
        return RuntimeContextBridge()

    def test_execute_returns_error_when_scope_not_found(self):
        bridge = self._make_bridge()
        result = bridge.execute("nonexistent_scope_xyz_12345")
        assert "error" in result

    def test_execute_finds_scope_in_caller_locals(self):
        bridge = self._make_bridge()
        main = lambda: None  # noqa: E731 - 'main' is intentionally in locals
        result = bridge.execute("main")
        # Should resolve the lambda and return a context payload
        assert "current_scope" in result
        assert result["current_scope"] == "main"

    def test_execute_with_env_fallback(self):
        from evolution.agents import RuntimeContextBridge

        class FakeEnv:
            myobj = lambda: None  # noqa: E731 - 'myobj' is intentionally a class attribute

        bridge = RuntimeContextBridge(runtime_environment=FakeEnv())
        result = bridge.execute("myobj")
        assert "current_scope" in result or "error" in result

    def test_serialize_state_depth_zero(self):
        bridge = self._make_bridge()
        assert bridge._serialize_state({"a": 1}, depth=0) == "{'a': 1}"

    def test_serialize_state_dict(self):
        bridge = self._make_bridge()
        result = bridge._serialize_state({"x": 42}, depth=1)
        assert result == {"x": "42"}

    def test_serialize_state_list(self):
        bridge = self._make_bridge()
        result = bridge._serialize_state([1, 2, 3], depth=1)
        assert result == ["1", "2", "3"]

    def test_serialize_state_tuple(self):
        bridge = self._make_bridge()
        result = bridge._serialize_state((10, 20), depth=1)
        assert result == ["10", "20"]

    def test_serialize_state_object_with_dict(self):
        bridge = self._make_bridge()

        class Simple:
            def __init__(self):
                self.val = "hello"

        result = bridge._serialize_state(Simple(), depth=2)
        assert isinstance(result, dict)

    def test_serialize_state_primitive(self):
        bridge = self._make_bridge()
        assert bridge._serialize_state(99, depth=2) == "99"

    def test_get_dependencies_for_function(self):
        bridge = self._make_bridge()

        def sample(x):
            return len(x) + int(x)

        deps = bridge._get_dependencies(sample)
        assert isinstance(deps, list)
        assert "len" in deps or "int" in deps

    def test_get_dependencies_for_non_function_returns_empty(self):
        bridge = self._make_bridge()
        result = bridge._get_dependencies(42)
        assert result == []

    def test_generate_instruction_named_object(self):
        bridge = self._make_bridge()

        def my_func():
            pass

        instruction = bridge._generate_instruction(my_func)
        assert "my_func" in instruction

    def test_generate_instruction_unnamed_object(self):
        bridge = self._make_bridge()
        instruction = bridge._generate_instruction(42)
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_history_returns_list(self):
        bridge = self._make_bridge()
        history = bridge._get_history()
        assert isinstance(history, list)

    def test_execute_with_include_history(self):
        bridge = self._make_bridge()
        main = lambda: None  # noqa: E731 - 'main' is intentionally in locals for scope lookup
        result = bridge.execute("main", include_history=True)
        if "error" not in result:
            assert "history" in result
