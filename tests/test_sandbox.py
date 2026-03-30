# tests/test_sandbox.py
# Unit tests for the Sandbox component

import os
import tempfile
import pytest
from evolution.sandbox import Sandbox


@pytest.fixture
def sandbox(tmp_path):
    return Sandbox(str(tmp_path))


# ---------------------------------------------------------------------------
# syntax_check
# ---------------------------------------------------------------------------

class TestSyntaxCheck:
    def test_valid_python(self, sandbox):
        assert sandbox.syntax_check("x = 1 + 2") is True

    def test_invalid_python(self, sandbox):
        assert sandbox.syntax_check("def foo(:\n    pass") is False

    def test_empty_string(self, sandbox):
        assert sandbox.syntax_check("") is True  # empty is syntactically valid

    def test_multiline_valid(self, sandbox):
        code = "def add(a, b):\n    return a + b\n"
        assert sandbox.syntax_check(code) is True


# ---------------------------------------------------------------------------
# verify_and_apply
# ---------------------------------------------------------------------------

class TestVerifyAndApply:
    def test_applies_valid_code(self, sandbox, tmp_path):
        target = tmp_path / "app.py"
        target.write_text("x = 0\n")
        new_code = "x = 42\n"
        result = sandbox.verify_and_apply(new_code, str(target))
        assert result is True
        assert target.read_text() == new_code

    def test_rejects_invalid_syntax(self, sandbox, tmp_path):
        target = tmp_path / "app.py"
        original = "x = 0\n"
        target.write_text(original)
        result = sandbox.verify_and_apply("def bad(:\n", str(target))
        assert result is False
        # Original file must remain untouched
        assert target.read_text() == original


# ---------------------------------------------------------------------------
# apply_feature_files
# ---------------------------------------------------------------------------

class TestApplyFeatureFiles:
    def test_creates_new_file(self, sandbox, tmp_path):
        feature_result = {
            "files_to_update": {},
            "new_files": {"utils.py": "def helper():\n    return True\n"},
        }
        result = sandbox.apply_feature_files(feature_result, str(tmp_path))
        assert result is True
        assert (tmp_path / "utils.py").exists()

    def test_creates_new_file_in_subdir(self, sandbox, tmp_path):
        feature_result = {
            "files_to_update": {},
            "new_files": {"subdir/helper.py": "x = 1\n"},
        }
        result = sandbox.apply_feature_files(feature_result, str(tmp_path))
        assert result is True
        assert (tmp_path / "subdir" / "helper.py").exists()

    def test_skips_invalid_new_file(self, sandbox, tmp_path):
        feature_result = {
            "files_to_update": {},
            "new_files": {"bad.py": "def bad(:\n"},
        }
        result = sandbox.apply_feature_files(feature_result, str(tmp_path))
        assert result is False  # overall success should be False

    def test_updates_existing_file(self, sandbox, tmp_path):
        existing = tmp_path / "app.py"
        existing.write_text("x = 0\n")
        feature_result = {
            "files_to_update": {"app.py": "x = 99\n"},
            "new_files": {},
        }
        result = sandbox.apply_feature_files(feature_result, str(tmp_path))
        assert result is True
        assert existing.read_text() == "x = 99\n"

    def test_empty_feature_result_returns_false(self, sandbox, tmp_path):
        result = sandbox.apply_feature_files(None, str(tmp_path))
        assert result is False
