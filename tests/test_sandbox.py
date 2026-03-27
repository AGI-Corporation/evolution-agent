# tests/test_sandbox.py

import os
import pytest
from unittest.mock import patch, MagicMock, mock_open
from evolution.sandbox import Sandbox


class TestSandboxSyntaxCheck:
    def _make_sandbox(self, tmp_path):
        return Sandbox(str(tmp_path))

    def test_valid_python_returns_true(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        assert sandbox.syntax_check("def foo():\n    return 42\n") is True

    def test_invalid_syntax_returns_false(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        assert sandbox.syntax_check("def foo(\n    return 1\n") is False

    def test_empty_string_is_valid_syntax(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        assert sandbox.syntax_check("") is True

    def test_multiline_valid_code(self, tmp_path):
        code = (
            "import os\n"
            "class Foo:\n"
            "    def bar(self, x):\n"
            "        return x + 1\n"
        )
        sandbox = self._make_sandbox(tmp_path)
        assert sandbox.syntax_check(code) is True

    def test_unclosed_string_is_invalid(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        assert sandbox.syntax_check('x = "unclosed') is False


class TestSandboxRunTests:
    def _make_sandbox(self, tmp_path):
        return Sandbox(str(tmp_path))

    def test_no_tests_directory_returns_true(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        # tmp_path has no 'tests' subdir by default
        assert sandbox.run_tests() is True

    def test_tests_pass_returns_true(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        sandbox = self._make_sandbox(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1 passed"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            assert sandbox.run_tests() is True

    def test_tests_fail_returns_false(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        sandbox = self._make_sandbox(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "1 failed"
        mock_result.stderr = "AssertionError"
        with patch("subprocess.run", return_value=mock_result):
            assert sandbox.run_tests() is False

    def test_run_tests_calls_pytest_with_correct_args(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        sandbox = self._make_sandbox(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            sandbox.run_tests()
        call_args = mock_run.call_args[0][0]
        assert "pytest" in call_args
        assert "tests/" in call_args


class TestSandboxVerifyAndApply:
    def _make_sandbox(self, tmp_path):
        return Sandbox(str(tmp_path))

    def test_invalid_syntax_rejected(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        target = tmp_path / "target.py"
        target.write_text("old code")
        result = sandbox.verify_and_apply("def bad(\n    pass\n", str(target))
        assert result is False
        assert target.read_text() == "old code"

    def test_successful_apply_overwrites_target(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        target = tmp_path / "target.py"
        target.write_text("# old")
        new_code = "def foo():\n    return 1\n"
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = sandbox.verify_and_apply(new_code, str(target))
        assert result is True
        assert target.read_text() == new_code

    def test_compile_check_failure_returns_false(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        target = tmp_path / "target.py"
        target.write_text("# old")
        new_code = "def foo():\n    return 1\n"
        mock_result = MagicMock(returncode=1, stdout="", stderr="compile error")
        with patch("subprocess.run", return_value=mock_result):
            result = sandbox.verify_and_apply(new_code, str(target))
        assert result is False
        assert target.read_text() == "# old"

    def test_temp_file_cleaned_up_on_success(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        target = tmp_path / "target.py"
        target.write_text("# old")
        new_code = "x = 1\n"
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            sandbox.verify_and_apply(new_code, str(target))
        # No .py temp files should remain (only the target itself)
        py_files = list(tmp_path.glob("tmp*.py"))
        assert len(py_files) == 0

    def test_temp_file_cleaned_up_on_failure(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        target = tmp_path / "target.py"
        target.write_text("# old")
        new_code = "x = 1\n"
        mock_result = MagicMock(returncode=1, stdout="", stderr="err")
        with patch("subprocess.run", return_value=mock_result):
            sandbox.verify_and_apply(new_code, str(target))
        py_files = list(tmp_path.glob("tmp*.py"))
        assert len(py_files) == 0

    def test_exception_during_apply_returns_false(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        target = tmp_path / "target.py"
        target.write_text("# old")
        new_code = "x = 1\n"
        with patch("subprocess.run", side_effect=RuntimeError("unexpected")):
            result = sandbox.verify_and_apply(new_code, str(target))
        assert result is False


class TestSandboxApplyFeatureFiles:
    def _make_sandbox(self, tmp_path):
        return Sandbox(str(tmp_path))

    def test_none_feature_result_returns_false(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        assert sandbox.apply_feature_files(None, str(tmp_path)) is False

    def test_empty_feature_result_returns_true(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        result = sandbox.apply_feature_files(
            {"files_to_update": {}, "new_files": {}}, str(tmp_path)
        )
        assert result is True

    def test_update_existing_file_success(self, tmp_path):
        existing = tmp_path / "main_app.py"
        existing.write_text("# old")
        sandbox = self._make_sandbox(tmp_path)
        new_code = "def foo(): pass\n"
        mock_run = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_run):
            result = sandbox.apply_feature_files(
                {"files_to_update": {"main_app.py": new_code}, "new_files": {}},
                str(tmp_path),
            )
        assert result is True
        assert existing.read_text() == new_code

    def test_new_file_created_with_valid_syntax(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        new_code = "def bar(): return 99\n"
        result = sandbox.apply_feature_files(
            {"files_to_update": {}, "new_files": {"helpers.py": new_code}},
            str(tmp_path),
        )
        assert result is True
        assert (tmp_path / "helpers.py").read_text() == new_code

    def test_new_file_with_invalid_syntax_skipped(self, tmp_path):
        sandbox = self._make_sandbox(tmp_path)
        bad_code = "def bad(\n    pass\n"
        result = sandbox.apply_feature_files(
            {"files_to_update": {}, "new_files": {"broken.py": bad_code}},
            str(tmp_path),
        )
        assert result is False
        assert not (tmp_path / "broken.py").exists()

    def test_update_failure_marks_all_success_false(self, tmp_path):
        existing = tmp_path / "main_app.py"
        existing.write_text("# old")
        sandbox = self._make_sandbox(tmp_path)
        bad_code = "def bad(\n    pass\n"
        result = sandbox.apply_feature_files(
            {"files_to_update": {"main_app.py": bad_code}, "new_files": {}},
            str(tmp_path),
        )
        assert result is False
