# evolution/agents.py
# Agent definitions: Observer, Architect, Auditor, Planner

import os
import json
import inspect
import logging
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except ImportError:
    client = None
    print("Warning: OpenAI client not installed. Running in simulation mode.")


class BaseAgent:
    def __init__(self, name):
        self.name = name

    def act(self, context):
        raise NotImplementedError

    def _call_llm(self, prompt, model="gpt-4o"):
        """Call the LLM with a prompt and return the response."""
        if client is None:
            print(f"[{self.name}] Simulation mode: No LLM client available.")
            return None
        logger.debug("[%s] LLM prompt (%d chars):\n%s", self.name, len(prompt), prompt)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        content = response.choices[0].message.content
        logger.debug("[%s] LLM response (%d chars):\n%s", self.name, len(content), content)
        return content


class ObserverAgent(BaseAgent):
    """
    Monitors logs and metrics to detect anomalies or opportunities.
    The Senses of the system.
    """
    def __init__(self):
        super().__init__("Observer")

    def scan_logs(self, log_path):
        """Read the last 50 lines of the log file."""
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()[-50:]
                return "".join(lines)
        except FileNotFoundError:
            return ""

    def act(self, log_path):
        """
        Analyze the log content and return a structured issue dict,
        or None if no issues are found.
        """
        log_content = self.scan_logs(log_path)
        if not log_content.strip():
            return None

        print(f"[{self.name}] Analyzing logs...")
        logger.debug("[%s] Log content (%d chars):\n%s", self.name, len(log_content), log_content)
        issue = {
            "type": "unknown",
            "log_excerpt": log_content[-500:],
            "timestamp": datetime.now().isoformat(),
        }

        # Detect common error patterns
        error_keywords = [
            "Error", "Exception", "Traceback", "CRITICAL", "FATAL",
            "ZeroDivisionError", "NameError", "TypeError", "AttributeError",
        ]
        for keyword in error_keywords:
            if keyword in log_content:
                issue["type"] = keyword
                break

        if issue["type"] == "unknown" and log_content.strip():
            issue["type"] = "anomaly"

        return issue if issue["type"] != "unknown" else None


class ArchitectAgent(BaseAgent):
    """
    Reads the current source code and generates a fix patch via LLM.
    The Brain of the system.
    """
    def __init__(self):
        super().__init__("Architect")

    def act(self, issue, source_code):
        """
        Generate a code patch to fix the detected issue.
        Returns the patched code as a string.
        """
        print(f"[{self.name}] Generating fix for issue: {issue['type']}")

        prompt = f"""You are a Senior Python Developer. Your task is to fix a bug in the code below.

CURRENT SOURCE CODE:
```python
{source_code}
```

ERROR DETECTED:
{issue['log_excerpt']}

Instructions:
- Fix the bug. Do NOT change the overall structure or functionality.
- Return ONLY the complete fixed Python source code, no explanations.
- The output must be valid, runnable Python.

FIXED CODE:"""

        fixed_code = self._call_llm(prompt)
        if fixed_code:
            # Strip markdown code fences if present
            if fixed_code.startswith("```"):
                lines = fixed_code.split("\n")
                fixed_code = "\n".join(lines[1:-1])
        logger.debug("[%s] Generated patch (%d chars):\n%s", self.name, len(fixed_code) if fixed_code else 0, fixed_code or "")
        return fixed_code


class AuditorAgent(BaseAgent):
    """
    Reviews patches for syntax errors before applying them.
    The Immune System of the system.
    """
    def __init__(self):
        super().__init__("Auditor")

    def act(self, code_patch):
        """
        Validate the patch. Returns True if safe to apply, False otherwise.
        """
        print(f"[{self.name}] Auditing patch...")
        if not code_patch or not code_patch.strip():
            print(f"[{self.name}] Rejected: Empty patch.")
            return False

        try:
            import ast
            ast.parse(code_patch)
            print(f"[{self.name}] Syntax check passed.")
            return True
        except SyntaxError as e:
            print(f"[{self.name}] Rejected: Syntax error in patch: {e}")
            return False


class PlannerAgent(BaseAgent):
    """
    Plans and generates new features based on requirements.
    The Growth Engine of the system.
    """
    def __init__(self):
        super().__init__("Planner")

    def implement_feature(self, requirement, current_files):
        """
        requirement: dict containing 'name' and 'description'
        current_files: dict of filename -> content
        Returns: dict with 'files_to_update' and 'new_files'
        """
        print(f"[{self.name}] Implementing feature: {requirement['name']}")

        context = ""
        for filename, content in current_files.items():
            context += f"\n--- FILE: {filename} ---\n{content}\n"

        prompt = f"""You are a Senior Python Developer. Implement the requested feature.

EXISTING CODEBASE:
{context}

FEATURE REQUEST:
Name: {requirement['name']}
Description: {requirement['description']}

OUTPUT FORMAT (valid JSON only, no markdown):
{{
    "plan": "Brief description of changes",
    "files_to_update": {{
        "filename.py": "full new code for this file"
    }},
    "new_files": {{
        "new_filename.py": "code for new file"
    }}
}}"""

        response = self._call_llm(prompt)
        if not response:
            return None

        try:
            # Strip markdown if present
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1])
            result = json.loads(response)
            logger.debug("[%s] Parsed feature plan: %s", self.name, result.get("plan", "N/A"))
            return result
        except json.JSONDecodeError as e:
            print(f"[{self.name}] Failed to parse LLM response as JSON: {e}")
            return None

    def act(self, context):
        """Alias for implement_feature when used in generic loop."""
        return self.implement_feature(
            context.get("requirement", {}),
            context.get("current_files", {})
        )


class RuntimeContextBridge:
    """
    Based on the interplaynetary/playtime concept.
    Inspects the live runtime state to generate context for Agents and Humans.
    Prevents 'blind coding' by giving agents a mental model of the current state.
    """
    def __init__(self, runtime_environment=None):
        self.env = runtime_environment

    def execute(self, scope_name="main", depth=2, include_history=False):
        """
        Capture the current execution state and format it as structured context.
        """
        try:
            frame = inspect.currentframe().f_back
            local_vars = frame.f_locals

            target_obj = local_vars.get(scope_name)
            if target_obj is None and self.env:
                target_obj = getattr(self.env, scope_name, None)

            if target_obj is None:
                return {"error": f"Scope '{scope_name}' not found in current runtime."}

            # Capture source code if possible
            try:
                source_code = inspect.getsource(target_obj)
            except (TypeError, OSError):
                source_code = "N/A (Primitive or Built-in)"

            # Serialize runtime values
            runtime_values = self._serialize_state(target_obj, depth)

            context_payload = {
                "current_scope": scope_name,
                "source_snapshot": source_code,
                "runtime_values": runtime_values,
                "dependency_map": self._get_dependencies(target_obj),
                "diff_context": self._generate_instruction(target_obj),
            }

            if include_history:
                context_payload["history"] = self._get_history()

            return context_payload

        except Exception as e:
            return {"error": str(e)}

    def _serialize_state(self, obj, depth):
        if depth == 0:
            return str(obj)
        if isinstance(obj, dict):
            return {k: self._serialize_state(v, depth - 1) for k, v in list(obj.items())[:10]}
        if isinstance(obj, (list, tuple)):
            return [self._serialize_state(i, depth - 1) for i in obj[:10]]
        if hasattr(obj, "__dict__"):
            return self._serialize_state(obj.__dict__, depth - 1)
        return str(obj)

    def _get_dependencies(self, obj):
        try:
            if inspect.isfunction(obj) or inspect.ismethod(obj):
                code = obj.__code__
                return list(code.co_names)
            return []
        except Exception:
            return []

    def _generate_instruction(self, obj):
        return (
            f"To modify '{obj.__name__ if hasattr(obj, '__name__') else type(obj).__name__}', "
            f"inspect the source_snapshot and inject new code at the appropriate location."
        )

    def _get_history(self):
        return ["history tracking not yet implemented"]
