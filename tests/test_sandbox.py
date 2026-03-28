# tests/test_sandbox.py
# Tests for evolution/sandbox.py

import os
import subprocess
import tempfile
import pytest
from unittest.mock import MagicMock, patch, call
from evolution.sandbox import Sandbox


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project root."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "tests").mkdir()
    return tmp_path


@pytest.fixture
def sandbox(tmp_project):
    return Sandbox(str(tmp_project))


# ---------------------------------------------------------------------------
# syntax_check
# ---------------------------------------------------------------------------

class TestSyntaxCheck:
    def test_valid_python(self, sandbox):
        code = "def hello():\n    return 42\n"
        assert sandbox.syntax_check(code) is True

    def test_invalid_python(self, sandbox):
        code = "def broken(:\n    pass\n"
        assert sandbox.syntax_check(code) is False

    def test_empty_string_is_valid_syntax(self, sandbox):
        assert sandbox.syntax_check("") is True

    def test_complex_valid_module(self, sandbox):
        code = (
            "import os\nimport json\n\n"
            "class Foo:\n    def bar(self): pass\n\n"
            "def main():\n    pass\n"
        )
        assert sandbox.syntax_check(code) is True


# ---------------------------------------------------------------------------
# run_tests
# ---------------------------------------------------------------------------

class TestRunTests:
    def test_no_tests_directory_returns_true(self, tmp_path):
        sb = Sandbox(str(tmp_path))  # no tests/ dir
        assert sb.run_tests() is True

    def test_tests_pass_returns_true(self, sandbox):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            assert sandbox.run_tests() is True

    def test_tests_fail_returns_false(self, sandbox):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "FAILED test_foo"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            assert sandbox.run_tests() is False


# ---------------------------------------------------------------------------
# verify_and_apply
# ---------------------------------------------------------------------------

class TestVerifyAndApply:
    def test_invalid_syntax_returns_false(self, sandbox, tmp_project):
        target = str(tmp_project / "main_app.py")
        result = sandbox.verify_and_apply("def broken(:\n    pass", target)
        assert result is False

    def test_valid_code_compile_ok_writes_file(self, sandbox, tmp_project):
        target = str(tmp_project / "main_app.py")
        valid_code = "def hello():\n    return 42\n"
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = sandbox.verify_and_apply(valid_code, target)
        assert result is True
        with open(target) as f:
            assert f.read() == valid_code

    def test_compile_check_fails_returns_false(self, sandbox, tmp_project):
        target = str(tmp_project / "main_app.py")
        valid_code = "def hello():\n    return 42\n"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "compile error"
        with patch("subprocess.run", return_value=mock_result):
            result = sandbox.verify_and_apply(valid_code, target)
        assert result is False

    def test_temp_file_cleaned_up_on_success(self, sandbox, tmp_project):
        target_path = tmp_project / "main_app.py"
        target_path.write_text("# pre-existing")  # ensure target already exists
        target = str(target_path)
        valid_code = "x = 1\n"
        mock_result = MagicMock()
        mock_result.returncode = 0
        tmp_files_before = set(tmp_project.iterdir())
        with patch("subprocess.run", return_value=mock_result):
            sandbox.verify_and_apply(valid_code, target)
        tmp_files_after = set(tmp_project.iterdir())
        # No extra .py temp files should remain
        new_py_files = [f for f in (tmp_files_after - tmp_files_before) if f.suffix == ".py"]
        assert len(new_py_files) == 0

    def test_temp_file_cleaned_up_on_failure(self, sandbox, tmp_project):
        target = str(tmp_project / "main_app.py")
        valid_code = "x = 1\n"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        tmp_files_before = set(tmp_project.iterdir())
        with patch("subprocess.run", return_value=mock_result):
            sandbox.verify_and_apply(valid_code, target)
        tmp_files_after = set(tmp_project.iterdir())
        new_py_files = [f for f in (tmp_files_after - tmp_files_before) if f.suffix == ".py"]
        assert len(new_py_files) == 0

    def test_exception_during_apply_returns_false(self, sandbox, tmp_project):
        target = str(tmp_project / "main_app.py")
        valid_code = "x = 1\n"
        with patch("subprocess.run", side_effect=Exception("unexpected")):
            result = sandbox.verify_and_apply(valid_code, target)
        assert result is False


# ---------------------------------------------------------------------------
# apply_feature_files
# ---------------------------------------------------------------------------

class TestApplyFeatureFiles:
    def test_none_input_returns_false(self, sandbox, tmp_project):
        assert sandbox.apply_feature_files(None, str(tmp_project)) is False

    def test_empty_result_returns_true(self, sandbox, tmp_project):
        result = sandbox.apply_feature_files(
            {"files_to_update": {}, "new_files": {}}, str(tmp_project)
        )
        assert result is True

    def test_update_existing_file_success(self, sandbox, tmp_project):
        target = tmp_project / "main_app.py"
        target.write_text("old content")
        new_code = "x = 1\n"
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = sandbox.apply_feature_files(
                {"files_to_update": {"main_app.py": new_code}, "new_files": {}},
                str(tmp_project)
            )
        assert result is True
        assert target.read_text() == new_code

    def test_update_file_failure_returns_false(self, sandbox, tmp_project):
        new_code = "def broken(:\n    pass\n"  # syntax error
        result = sandbox.apply_feature_files(
            {"files_to_update": {"main_app.py": new_code}, "new_files": {}},
            str(tmp_project)
        )
        assert result is False

    def test_create_new_file_valid_syntax(self, sandbox, tmp_project):
        new_code = "def new_thing():\n    pass\n"
        result = sandbox.apply_feature_files(
            {"files_to_update": {}, "new_files": {"new_module.py": new_code}},
            str(tmp_project)
        )
        assert result is True
        assert (tmp_project / "new_module.py").exists()
        assert (tmp_project / "new_module.py").read_text() == new_code

    def test_create_new_file_invalid_syntax_skips(self, sandbox, tmp_project):
        bad_code = "def broken(:\n    pass\n"
        result = sandbox.apply_feature_files(
            {"files_to_update": {}, "new_files": {"broken.py": bad_code}},
            str(tmp_project)
        )
        assert result is False
        assert not (tmp_project / "broken.py").exists()

    def test_create_new_file_in_subdir(self, sandbox, tmp_project):
        new_code = "x = 1\n"
        result = sandbox.apply_feature_files(
            {"files_to_update": {}, "new_files": {"subdir/module.py": new_code}},
            str(tmp_project)
        )
        assert result is True
        assert (tmp_project / "subdir" / "module.py").exists()
