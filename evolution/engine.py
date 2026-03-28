# evolution/engine.py
# Main evolution loop controller

import os
import json
import logging
import time
from datetime import datetime
from evolution.agents import ObserverAgent, ArchitectAgent, AuditorAgent
from evolution.sandbox import Sandbox

logger = logging.getLogger(__name__)


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
        logger.debug("[Engine] === Step 1: Observe ===")

        # Step 1: Observe
        issue = self.observer.act(self.log_path)
        if not issue:
            print("[Engine] System is healthy. No evolution required.")
            return False

        print(f"[Engine] Issue detected: {issue['type']}")
        logger.debug("[Engine] Issue details:\n%s", json.dumps(issue, indent=2))

        # Step 2: Read source
        logger.debug("[Engine] === Step 2: Read Source ===")
        source_code = self.read_source()
        if not source_code:
            print("[Engine] Cannot read source. Aborting cycle.")
            return False
        logger.debug("[Engine] Source code read (%d chars)", len(source_code))

        # Step 3: Architect generates fix
        logger.debug("[Engine] === Step 3: Architect ===")
        proposed_patch = self.architect.act(issue, source_code)
        if not proposed_patch:
            print("[Engine] Architect failed to generate a patch. Aborting cycle.")
            return False
        logger.debug("[Engine] Proposed patch (%d chars)", len(proposed_patch))

        # Step 4: Auditor validates
        logger.debug("[Engine] === Step 4: Audit ===")
        if not self.auditor.act(proposed_patch):
            print("[Engine] Auditor rejected the patch. Evolution aborted.")
            return False
        logger.debug("[Engine] Patch passed auditor validation")

        # Step 5: Sandbox applies
        logger.debug("[Engine] === Step 5: Apply ===")
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
            logger.debug("[Engine] === Cycle %d ===", cycle_count + 1)
            self.run_evolution_cycle()
            cycle_count += 1

            if max_cycles and cycle_count >= max_cycles:
                print(f"[Engine] Reached max cycles ({max_cycles}). Stopping.")
                break

            logger.debug("[Engine] Cycle complete. Sleeping %ds...", interval)
            print(f"[Engine] Sleeping for {interval}s...")
            time.sleep(interval)


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Evolution Engine")
    parser.add_argument(
        "root",
        nargs="?",
        default=os.getcwd(),
        help="Project root directory (default: current directory)",
    )
    parser.add_argument(
        "--debug", "-debug",
        action="store_true",
        help="Enable verbose debug logging (shows LLM prompts, responses, and detailed step traces)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    engine = EvolutionEngine(args.root)
    engine.run()
