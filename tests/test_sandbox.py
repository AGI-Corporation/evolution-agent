# tests/test_sandbox.py
# Tests for evolution/sandbox.py

import os
import pytest


@pytest.fixture()
def sandbox(tmp_path):
    from evolution.sandbox import Sandbox
    return Sandbox(str(tmp_path))


class TestSandboxSyntaxCheck:
    def test_valid_code(self, sandbox):
        assert sandbox.syntax_check("def foo(): return 1") is True

    def test_invalid_code(self, sandbox):
        assert sandbox.syntax_check("def foo( return 1") is False

    def test_multiline_valid(self, sandbox):
        code = "import os\ndef greet(name):\n    return f'Hi {name}'\n"
        assert sandbox.syntax_check(code) is True

    def test_empty_string(self, sandbox):
        # Empty string is valid Python
        assert sandbox.syntax_check("") is True


class TestSandboxVerifyAndApply:
    def test_applies_valid_patch(self, sandbox, tmp_path):
        target = tmp_path / "target.py"
        target.write_text("# original\n")
        result = sandbox.verify_and_apply("def updated(): return True\n", str(target))
        assert result is True
        assert "def updated" in target.read_text()

    def test_rejects_syntax_error(self, sandbox, tmp_path):
        target = tmp_path / "target.py"
        target.write_text("# original\n")
        result = sandbox.verify_and_apply("def broken( return 1", str(target))
        assert result is False
        # Original file must be untouched
        assert target.read_text() == "# original\n"

    def test_rejects_empty_code(self, sandbox, tmp_path):
        target = tmp_path / "target.py"
        target.write_text("# original\n")
        # Empty is valid Python but produces a valid (empty) compile
        result = sandbox.verify_and_apply("", str(target))
        # Should succeed (empty file is valid Python)
        assert result is True

    def test_no_temp_file_left_behind(self, sandbox, tmp_path):
        target = tmp_path / "target.py"
        target.write_text("# original\n")
        sandbox.verify_and_apply("x = 1\n", str(target))
        py_files = list(tmp_path.glob("*.py"))
        # Only the target file should remain
        assert all(f.name == "target.py" for f in py_files)


class TestSandboxApplyFeatureFiles:
    def test_creates_new_file(self, sandbox, tmp_path):
        feature_result = {
            "files_to_update": {},
            "new_files": {"newfile.py": "def hello(): return 'world'\n"},
        }
        result = sandbox.apply_feature_files(feature_result, str(tmp_path))
        assert result is True
        assert (tmp_path / "newfile.py").exists()

    def test_creates_nested_new_file(self, sandbox, tmp_path):
        feature_result = {
            "files_to_update": {},
            "new_files": {"sub/dir/newfile.py": "x = 1\n"},
        }
        result = sandbox.apply_feature_files(feature_result, str(tmp_path))
        assert result is True
        assert (tmp_path / "sub" / "dir" / "newfile.py").exists()

    def test_updates_existing_file(self, sandbox, tmp_path):
        existing = tmp_path / "app.py"
        existing.write_text("# old\n")
        feature_result = {
            "files_to_update": {"app.py": "# new\ndef func(): pass\n"},
            "new_files": {},
        }
        result = sandbox.apply_feature_files(feature_result, str(tmp_path))
        assert result is True
        assert "# new" in existing.read_text()

    def test_skips_new_file_with_syntax_error(self, sandbox, tmp_path):
        feature_result = {
            "files_to_update": {},
            "new_files": {"bad.py": "def broken( return 1"},
        }
        result = sandbox.apply_feature_files(feature_result, str(tmp_path))
        assert result is False
        assert not (tmp_path / "bad.py").exists()

    def test_returns_false_on_none(self, sandbox, tmp_path):
        assert sandbox.apply_feature_files(None, str(tmp_path)) is False

    def test_empty_result(self, sandbox, tmp_path):
        feature_result = {"files_to_update": {}, "new_files": {}}
        result = sandbox.apply_feature_files(feature_result, str(tmp_path))
        assert result is True


class TestSandboxRunTests:
    def test_no_tests_dir_returns_true(self, tmp_path):
        from evolution.sandbox import Sandbox
        sb = Sandbox(str(tmp_path))
        # No tests/ directory -> skipped, treated as passing
        assert sb.run_tests() is True
