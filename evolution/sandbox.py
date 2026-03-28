# evolution/sandbox.py
# Safe code execution and test runner environment

import subprocess
import tempfile
import os
import ast
import logging

logger = logging.getLogger(__name__)


class Sandbox:
    """
    Safe code execution environment.
    Verifies code before allowing it to overwrite the target file.
    """

    def __init__(self, project_root):
        self.project_root = project_root

    def run_tests(self):
        """
        Runs the project's pytest test suite.
        Returns True if all tests pass, False otherwise.
        """
        print("[Sandbox] Running unit tests...")
        tests_dir = os.path.join(self.project_root, "tests")

        if not os.path.exists(tests_dir):
            print("[Sandbox] No tests/ directory found. Skipping test run.")
            return True

        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-q", "--tb=short"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=120,
        )

        logger.debug("[Sandbox] pytest stdout:\n%s", result.stdout)
        logger.debug("[Sandbox] pytest stderr:\n%s", result.stderr)

        if result.returncode == 0:
            print("[Sandbox] Tests Passed.")
            return True
        else:
            print(f"[Sandbox] Tests Failed:\n{result.stdout}\n{result.stderr}")
            return False

    def syntax_check(self, code):
        """
        Perform a static syntax check on the code string.
        Returns True if syntax is valid, False otherwise.
        """
        try:
            ast.parse(code)
            print("[Sandbox] Syntax check passed.")
            return True
        except SyntaxError as e:
            print(f"[Sandbox] Syntax error: {e}")
            return False

    def verify_and_apply(self, new_code, target_file):
        """
        Writes code to a temp file, runs syntax check,
        then overwrites the target file if safe.
        Returns True if successfully applied.
        """
        logger.debug("[Sandbox] verify_and_apply: target=%s code_size=%d chars", target_file, len(new_code))

        # Step 1: Syntax check
        if not self.syntax_check(new_code):
            print("[Sandbox] Rejected: Syntax error. Target file NOT modified.")
            return False

        # Step 2: Write to temp file for safety
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, dir=self.project_root
            ) as tmp:
                tmp.write(new_code)
                tmp_path = tmp.name
            logger.debug("[Sandbox] Wrote temp file: %s", tmp_path)

            # Step 3: Try executing the temp file to check for runtime errors
            result = subprocess.run(
                ["python", "-c", f"import py_compile; py_compile.compile('{tmp_path}', doraise=True)"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            logger.debug("[Sandbox] py_compile stdout: %s", result.stdout)
            logger.debug("[Sandbox] py_compile stderr: %s", result.stderr)

            if result.returncode != 0:
                print(f"[Sandbox] Compile check failed: {result.stderr}")
                return False

            # Step 4: Overwrite target file
            with open(target_file, "w") as f:
                f.write(new_code)

            print(f"[Sandbox] Successfully applied patch to {target_file}")
            return True

        except Exception as e:
            print(f"[Sandbox] Error during verify_and_apply: {e}")
            return False

        finally:
            # Clean up temp file
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    def apply_feature_files(self, feature_result, project_root):
        """
        Apply files from a PlannerAgent feature result.
        feature_result: dict with 'files_to_update' and 'new_files'
        Returns True if all files were applied successfully.
        """
        if not feature_result:
            return False

        all_success = True

        # Update existing files
        for filename, code in feature_result.get("files_to_update", {}).items():
            target = os.path.join(project_root, filename)
            success = self.verify_and_apply(code, target)
            if not success:
                all_success = False
                print(f"[Sandbox] Failed to apply update to {filename}")

        # Create new files
        for filename, code in feature_result.get("new_files", {}).items():
            target = os.path.join(project_root, filename)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if not self.syntax_check(code):
                print(f"[Sandbox] Skipping new file {filename} due to syntax error.")
                all_success = False
                continue
            with open(target, "w") as f:
                f.write(code)
            print(f"[Sandbox] Created new file: {filename}")

        return all_success
