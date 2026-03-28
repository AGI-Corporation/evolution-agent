# tests/test_agents.py
# Tests for evolution/agents.py

import ast
import json
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch, mock_open
from evolution.agents import (
    BaseAgent,
    ObserverAgent,
    ArchitectAgent,
    AuditorAgent,
    PlannerAgent,
    RuntimeContextBridge,
)


# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------

class TestBaseAgent:
    def test_act_raises_not_implemented(self):
        agent = BaseAgent("TestAgent")
        with pytest.raises(NotImplementedError):
            agent.act(None)

    def test_name_is_set(self):
        agent = BaseAgent("MyAgent")
        assert agent.name == "MyAgent"

    def test_call_llm_no_client(self):
        """When OpenAI client is unavailable, _call_llm returns None."""
        agent = BaseAgent("TestAgent")
        with patch("evolution.agents.client", None):
            result = agent._call_llm("some prompt")
        assert result is None

    def test_call_llm_with_client(self):
        """When client is available, it is called and response returned."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = "response text"
        agent = BaseAgent("TestAgent")
        with patch("evolution.agents.client", mock_client):
            result = agent._call_llm("prompt")
        assert result == "response text"


# ---------------------------------------------------------------------------
# ObserverAgent
# ---------------------------------------------------------------------------

class TestObserverAgent:
    def setup_method(self):
        self.agent = ObserverAgent()

    def test_name(self):
        assert self.agent.name == "Observer"

    def test_scan_logs_file_not_found(self):
        result = self.agent.scan_logs("/nonexistent/path/system.log")
        assert result == ""

    def test_scan_logs_returns_last_50_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            lines = [f"line {i}\n" for i in range(100)]
            f.writelines(lines)
            path = f.name
        try:
            result = self.agent.scan_logs(path)
            result_lines = result.splitlines()
            assert len(result_lines) == 50
            assert result_lines[0] == "line 50"
            assert result_lines[-1] == "line 99"
        finally:
            os.unlink(path)

    def test_scan_logs_fewer_than_50_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("line1\nline2\n")
            path = f.name
        try:
            result = self.agent.scan_logs(path)
            assert "line1" in result
            assert "line2" in result
        finally:
            os.unlink(path)

    def test_act_empty_log_returns_none(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("   \n")
            path = f.name
        try:
            result = self.agent.act(path)
            assert result is None
        finally:
            os.unlink(path)

    def test_act_missing_log_returns_none(self):
        result = self.agent.act("/no/such/file.log")
        assert result is None

    @pytest.mark.parametrize("keyword", [
        "Error", "Exception", "Traceback", "CRITICAL", "FATAL",
        "ZeroDivisionError", "NameError", "TypeError", "AttributeError",
    ])
    def test_act_detects_error_keywords(self, keyword):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(f"Something went wrong: {keyword}: blah blah\n")
            path = f.name
        try:
            result = self.agent.act(path)
            assert result is not None
            assert result["type"] == keyword
        finally:
            os.unlink(path)

    def test_act_returns_anomaly_for_unknown_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("some unusual log content without known keywords\n")
            path = f.name
        try:
            result = self.agent.act(path)
            assert result is not None
            assert result["type"] == "anomaly"
        finally:
            os.unlink(path)

    def test_act_result_has_timestamp(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("Error: something failed\n")
            path = f.name
        try:
            result = self.agent.act(path)
            assert "timestamp" in result
        finally:
            os.unlink(path)

    def test_act_result_has_log_excerpt(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("Error: something failed\n")
            path = f.name
        try:
            result = self.agent.act(path)
            assert "log_excerpt" in result
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# ArchitectAgent
# ---------------------------------------------------------------------------

class TestArchitectAgent:
    def setup_method(self):
        self.agent = ArchitectAgent()

    def test_name(self):
        assert self.agent.name == "Architect"

    def test_act_no_client_returns_none(self):
        issue = {"type": "Error", "log_excerpt": "Error occurred"}
        with patch("evolution.agents.client", None):
            result = self.agent.act(issue, "def foo(): pass")
        assert result is None

    def test_act_strips_markdown_fences(self):
        mock_response = "```python\ndef fixed(): pass\n```"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = mock_response
        issue = {"type": "Error", "log_excerpt": "some error"}
        with patch("evolution.agents.client", mock_client):
            result = self.agent.act(issue, "def foo(): pass")
        assert result == "def fixed(): pass"

    def test_act_without_markdown_fences(self):
        mock_response = "def fixed(): pass"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = mock_response
        issue = {"type": "Error", "log_excerpt": "some error"}
        with patch("evolution.agents.client", mock_client):
            result = self.agent.act(issue, "def foo(): pass")
        assert result == "def fixed(): pass"

    def test_act_builds_prompt_with_issue_type(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = "fixed code"
        issue = {"type": "ZeroDivisionError", "log_excerpt": "division by zero"}
        with patch("evolution.agents.client", mock_client):
            self.agent.act(issue, "code")
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        assert "ZeroDivisionError" in messages[0]["content"] or "division by zero" in messages[0]["content"]


# ---------------------------------------------------------------------------
# AuditorAgent
# ---------------------------------------------------------------------------

class TestAuditorAgent:
    def setup_method(self):
        self.agent = AuditorAgent()

    def test_name(self):
        assert self.agent.name == "Auditor"

    def test_act_empty_patch_returns_false(self):
        assert self.agent.act("") is False

    def test_act_none_patch_returns_false(self):
        assert self.agent.act(None) is False

    def test_act_whitespace_only_returns_false(self):
        assert self.agent.act("   \n  ") is False

    def test_act_valid_syntax_returns_true(self):
        valid_code = "def hello():\n    return 'world'\n"
        assert self.agent.act(valid_code) is True

    def test_act_syntax_error_returns_false(self):
        bad_code = "def broken(:\n    pass\n"
        assert self.agent.act(bad_code) is False

    def test_act_complex_valid_code(self):
        code = (
            "import os\n"
            "class Foo:\n"
            "    def __init__(self):\n"
            "        self.x = 1\n"
            "    def bar(self):\n"
            "        return self.x * 2\n"
        )
        assert self.agent.act(code) is True


# ---------------------------------------------------------------------------
# PlannerAgent
# ---------------------------------------------------------------------------

class TestPlannerAgent:
    def setup_method(self):
        self.agent = PlannerAgent()

    def test_name(self):
        assert self.agent.name == "Planner"

    def test_implement_feature_no_client_returns_none(self):
        requirement = {"name": "feature-x", "description": "add feature x"}
        with patch("evolution.agents.client", None):
            result = self.agent.implement_feature(requirement, {"main.py": "pass"})
        assert result is None

    def test_implement_feature_valid_json_response(self):
        payload = {
            "plan": "add a new function",
            "files_to_update": {"main.py": "def new(): pass"},
            "new_files": {},
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = json.dumps(payload)
        requirement = {"name": "new-func", "description": "add new function"}
        with patch("evolution.agents.client", mock_client):
            result = self.agent.implement_feature(requirement, {"main.py": "pass"})
        assert result == payload

    def test_implement_feature_strips_markdown(self):
        payload = {"plan": "ok", "files_to_update": {}, "new_files": {}}
        response = f"```json\n{json.dumps(payload)}\n```"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = response
        requirement = {"name": "x", "description": "y"}
        with patch("evolution.agents.client", mock_client):
            result = self.agent.implement_feature(requirement, {})
        assert result == payload

    def test_implement_feature_invalid_json_returns_none(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = "not json at all"
        requirement = {"name": "x", "description": "y"}
        with patch("evolution.agents.client", mock_client):
            result = self.agent.implement_feature(requirement, {})
        assert result is None

    def test_act_delegates_to_implement_feature(self):
        payload = {"plan": "p", "files_to_update": {}, "new_files": {}}
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = json.dumps(payload)
        context = {
            "requirement": {"name": "x", "description": "y"},
            "current_files": {"main.py": "pass"},
        }
        with patch("evolution.agents.client", mock_client):
            result = self.agent.act(context)
        assert result == payload


# ---------------------------------------------------------------------------
# RuntimeContextBridge
# ---------------------------------------------------------------------------

class TestRuntimeContextBridge:
    def setup_method(self):
        self.bridge = RuntimeContextBridge()

    def test_serialize_state_depth_zero(self):
        result = self.bridge._serialize_state({"key": "value"}, 0)
        assert isinstance(result, str)

    def test_serialize_state_dict(self):
        result = self.bridge._serialize_state({"a": 1, "b": 2}, 2)
        assert isinstance(result, dict)
        assert "a" in result

    def test_serialize_state_list(self):
        result = self.bridge._serialize_state([1, 2, 3], 2)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_serialize_state_tuple(self):
        result = self.bridge._serialize_state((10, 20), 2)
        assert isinstance(result, list)

    def test_serialize_state_limits_large_collections(self):
        big_dict = {str(i): i for i in range(50)}
        result = self.bridge._serialize_state(big_dict, 1)
        assert len(result) <= 10

    def test_serialize_state_object_with_dict(self):
        class Obj:
            def __init__(self):
                self.x = 1
                self.y = 2
        result = self.bridge._serialize_state(Obj(), 2)
        assert isinstance(result, dict)

    def test_get_dependencies_function(self):
        def sample_func():
            return len([])
        deps = self.bridge._get_dependencies(sample_func)
        assert isinstance(deps, list)
        assert "len" in deps

    def test_get_dependencies_non_function(self):
        deps = self.bridge._get_dependencies("a string")
        assert deps == []

    def test_generate_instruction_with_name(self):
        def my_func():
            pass
        result = self.bridge._generate_instruction(my_func)
        assert "my_func" in result

    def test_generate_instruction_without_name(self):
        result = self.bridge._generate_instruction(42)
        assert isinstance(result, str)

    def test_get_history_returns_list(self):
        result = self.bridge._get_history()
        assert isinstance(result, list)

    def test_execute_unknown_scope_returns_error(self):
        result = self.bridge.execute(scope_name="nonexistent_scope_xyz")
        assert "error" in result

    def test_execute_with_runtime_environment(self):
        class FakeEnv:
            def __init__(self):
                self.my_scope = None
        env = FakeEnv()
        bridge = RuntimeContextBridge(runtime_environment=env)
        result = bridge.execute(scope_name="my_scope")
        assert "error" in result  # None scope triggers error
