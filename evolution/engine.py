# evolution/engine.py
# Main evolution loop controller

import os
import json
import time
from datetime import datetime
from evolution.agents import ObserverAgent, ArchitectAgent, AuditorAgent
from evolution.sandbox import Sandbox


class EvolutionEngine:
    """
    Main controller for the Evolution Loop.
    Orchestrates observation, code generation, validation, and application.
    """

    def __init__(self, project_root):
        self.project_root = project_root
        self.log_path = os.path.join(project_root, "logs", "system.log")
        self.target_file = os.path.join(project_root, "main_app.py")

        self.observer = ObserverAgent()
        self.architect = ArchitectAgent()
        self.auditor = AuditorAgent()
        self.sandbox = Sandbox(project_root)

        self.memory_file = os.path.join(project_root, "evolution", "memory.json")
        self._init_memory()

    def _init_memory(self):
        """Ensure memory.json exists."""
        if not os.path.exists(self.memory_file):
            with open(self.memory_file, "w") as f:
                json.dump([], f)

    def save_memory(self, issue, patch_preview):
        """Log a successful evolution to memory.json."""
        try:
            with open(self.memory_file, "r+") as f:
                data = json.load(f)
                data.append({
                    "timestamp": datetime.now().isoformat(),
                    "issue_type": issue.get("type", "unknown"),
                    "fix_preview": patch_preview[:200] + "..." if len(patch_preview) > 200 else patch_preview,
                })
                f.seek(0)
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[Engine] Failed to save memory: {e}")

    def read_source(self):
        """Read the current target file source code."""
        try:
            with open(self.target_file, "r") as f:
                return f.read()
        except FileNotFoundError:
            print(f"[Engine] Target file not found: {self.target_file}")
            return None

    def clear_log(self):
        """Clear the system log after a successful fix."""
        try:
            with open(self.log_path, "w") as f:
                f.write("")
            print("[Engine] Log cleared after successful evolution.")
        except Exception as e:
            print(f"[Engine] Failed to clear log: {e}")

    def run_evolution_cycle(self):
        """
        Execute a single evolution cycle:
        Observe -> Architect -> Audit -> Apply
        Returns True if an evolution was performed, False if system is healthy.
        """
        print(f"\n[{datetime.now().isoformat()}] Starting Evolution Cycle...")

        # Step 1: Observe
        issue = self.observer.act(self.log_path)
        if not issue:
            print("[Engine] System is healthy. No evolution required.")
            return False

        print(f"[Engine] Issue detected: {issue['type']}")

        # Step 2: Read source
        source_code = self.read_source()
        if not source_code:
            print("[Engine] Cannot read source. Aborting cycle.")
            return False

        # Step 3: Architect generates fix
        proposed_patch = self.architect.act(issue, source_code)
        if not proposed_patch:
            print("[Engine] Architect failed to generate a patch. Aborting cycle.")
            return False

        # Step 4: Auditor validates
        if not self.auditor.act(proposed_patch):
            print("[Engine] Auditor rejected the patch. Evolution aborted.")
            return False

        # Step 5: Sandbox applies
        success = self.sandbox.verify_and_apply(proposed_patch, self.target_file)
        if success:
            print(f"[Engine] Evolution Successful!")
            self.save_memory(issue, proposed_patch)
            self.clear_log()
            return True
        else:
            print("[Engine] Sandbox failed to apply patch. Evolution aborted.")
            return False

    def run(self, interval=30, max_cycles=None):
        """
        Run the evolution loop continuously.
        interval: seconds between cycles
        max_cycles: stop after N cycles (None = run forever)
        """
        print("[Engine] Evolution Engine started.")
        cycle_count = 0

        while True:
            self.run_evolution_cycle()
            cycle_count += 1

            if max_cycles and cycle_count >= max_cycles:
                print(f"[Engine] Reached max cycles ({max_cycles}). Stopping.")
                break

            print(f"[Engine] Sleeping for {interval}s...")
            time.sleep(interval)


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    engine = EvolutionEngine(root)
    engine.run()
