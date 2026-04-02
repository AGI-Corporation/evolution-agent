# evolution/supervisor.py
# Orchestrates all agents: bug fixing, feature planning, git integration

import os
import json
import time
from datetime import datetime
from evolution.agents import ObserverAgent, ArchitectAgent, AuditorAgent, PlannerAgent
from evolution.sandbox import Sandbox
from evolution.version_control import GitManager
from evolution.epoch_tracker import EpochTracker
from evolution.reporting import EvolutionReporter
from evolution.nanda_bridge import NANDABridge


class Supervisor:
    """
    The Supervisor orchestrates all agents and coordinates the full evolution loop.
    Handles both reactive bug-fixing and proactive feature implementation.

    Loop:
    1. Check for bugs (system.log) -> run bug fix cycle
    2. Check for feature requests (feature_queue.json) -> run feature cycle
    3. Sleep and repeat
    """

    def __init__(self, project_root):
        self.project_root = project_root
        self.log_path = os.path.join(project_root, "logs", "system.log")
        self.queue_path = os.path.join(project_root, "evolution", "feature_queue.json")
        self.memory_path = os.path.join(project_root, "evolution", "memory.json")
        self.target_file = os.path.join(project_root, "main_app.py")

        # Initialize components
        self.observer = ObserverAgent()
        self.architect = ArchitectAgent()
        self.planner = PlannerAgent()
        self.auditor = AuditorAgent()
        self.sandbox = Sandbox(project_root)
        self.git = GitManager(project_root)

        # Deep integrations: epoch tracking, reporting, and NANDA interop
        self.epoch_tracker = EpochTracker(project_root)
        self.reporter = EvolutionReporter(project_root)
        self.nanda = NANDABridge(node_id="evolution_supervisor")

        self._init_files()

    def _init_files(self):
        """Ensure all required files exist."""
        os.makedirs(os.path.join(self.project_root, "logs"), exist_ok=True)
        os.makedirs(os.path.join(self.project_root, "evolution"), exist_ok=True)

        if not os.path.exists(self.log_path):
            open(self.log_path, "w").close()

        if not os.path.exists(self.queue_path):
            with open(self.queue_path, "w") as f:
                json.dump([], f)

        if not os.path.exists(self.memory_path):
            with open(self.memory_path, "w") as f:
                json.dump([], f)

    def read_source(self, filepath=None):
        """Read a source file."""
        filepath = filepath or self.target_file
        try:
            with open(filepath, "r") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def save_memory(self, entry):
        """Append an entry to memory.json."""
        try:
            with open(self.memory_path, "r+") as f:
                data = json.load(f)
                data.append(entry)
                f.seek(0)
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[Supervisor] Memory save error: {e}")

    def clear_log(self):
        """Clear the system log after successful fix."""
        with open(self.log_path, "w") as f:
            f.write("")
        print("[Supervisor] Log cleared.")

    def process_bug_fix(self):
        """
        Reactive: Detect and fix bugs from the error log.
        Returns True if a fix was applied.
        """
        issue = self.observer.act(self.log_path)
        if not issue:
            return False

        print(f"[Supervisor] Bug detected: {issue['type']}")

        # Register this fix attempt as an agent version in the current epoch
        agent_version = self.epoch_tracker.register_agent(
            parent_id=None,
            mutation_params={
                "role": "bug_fix",
                "issue_type": issue["type"],
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Broadcast to NANDA so peer nodes are aware of the mutation task
        self.nanda.broadcast_mutation_sync({
            "type": "bug_fix",
            "issue": issue["type"],
            "agent_version": agent_version.version_id,
        })

        source_code = self.read_source()
        if not source_code:
            print("[Supervisor] Cannot read source for bug fix.")
            self.epoch_tracker.log_performance(agent_version.version_id, 0.0, status="failed")
            return False

        # Create a safety branch
        branch_name = self.git.create_evolution_branch(prefix="fix")
        if not branch_name:
            print("[Supervisor] Could not create safety branch. Proceeding without git branching.")

        # Generate and validate patch
        patch = self.architect.act(issue, source_code)
        if not patch or not self.auditor.act(patch):
            print("[Supervisor] Bug fix patch rejected.")
            self.epoch_tracker.log_performance(agent_version.version_id, 0.0, status="failed")
            if branch_name:
                self.git.checkout_branch("main")
            return False

        # Apply patch
        success = self.sandbox.verify_and_apply(patch, self.target_file)
        if success:
            # Run tests
            tests_passed = self.sandbox.run_tests()
            if tests_passed:
                # Commit the fix
                if branch_name:
                    self.git.commit_changes(f"fix: Auto-fix {issue['type']} - {datetime.now().isoformat()}")
                    self.git.merge_to_main(branch_name)
                self.epoch_tracker.log_performance(agent_version.version_id, 1.0, status="tested")
                self.save_memory({
                    "type": "bug_fix",
                    "timestamp": datetime.now().isoformat(),
                    "issue": issue["type"],
                    "agent_version": agent_version.version_id,
                    "status": "success",
                })
                self.clear_log()
                print(f"[Supervisor] Bug fix successful!")
                return True
            else:
                print("[Supervisor] Tests failed after patch. Rolling back.")
                self.epoch_tracker.log_performance(agent_version.version_id, 0.0, status="failed")
                if branch_name:
                    self.git.rollback()
                    self.git.checkout_branch("main")
                return False
        else:
            print("[Supervisor] Patch could not be applied.")
            self.epoch_tracker.log_performance(agent_version.version_id, 0.0, status="failed")
            if branch_name:
                self.git.checkout_branch("main")
            return False

    def load_feature_queue(self):
        """Load pending feature requests from feature_queue.json."""
        try:
            with open(self.queue_path, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def save_feature_queue(self, queue):
        """Save the updated feature queue."""
        with open(self.queue_path, "w") as f:
            json.dump(queue, f, indent=4)

    def process_feature_request(self):
        """
        Proactive: Implement features from the feature queue.
        Returns True if a feature was implemented.
        """
        queue = self.load_feature_queue()
        if not queue:
            return False

        requirement = queue.pop(0)
        print(f"[Supervisor] Processing feature: {requirement.get('name', 'unnamed')}")

        # Register this feature attempt as an agent version in the current epoch
        agent_version = self.epoch_tracker.register_agent(
            parent_id=None,
            mutation_params={
                "role": "feature",
                "feature_name": requirement.get("name", "unnamed"),
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Broadcast to NANDA so peer nodes are aware of the mutation task
        self.nanda.broadcast_mutation_sync({
            "type": "feature_implementation",
            "feature": requirement.get("name"),
            "agent_version": agent_version.version_id,
        })

        # Load current files for context
        current_files = {}
        for fname in ["main_app.py"]:
            content = self.read_source(os.path.join(self.project_root, fname))
            if content:
                current_files[fname] = content

        # Create a feature branch
        branch_name = self.git.create_evolution_branch(prefix="feature")

        # Plan the feature
        feature_result = self.planner.implement_feature(requirement, current_files)
        if not feature_result:
            print("[Supervisor] Planner failed to generate feature code.")
            self.epoch_tracker.log_performance(agent_version.version_id, 0.0, status="failed")
            self.save_feature_queue(queue)  # Remove from queue anyway
            if branch_name:
                self.git.checkout_branch("main")
            return False

        print(f"[Supervisor] Feature plan: {feature_result.get('plan', 'N/A')}")

        # Apply feature files
        success = self.sandbox.apply_feature_files(feature_result, self.project_root)
        if success:
            tests_passed = self.sandbox.run_tests()
            if tests_passed:
                if branch_name:
                    self.git.commit_changes(f"feat: {requirement.get('name', 'new-feature')} - {datetime.now().isoformat()}")
                    self.git.merge_to_main(branch_name)
                self.epoch_tracker.log_performance(agent_version.version_id, 1.0, status="tested")
                self.save_memory({
                    "type": "feature",
                    "timestamp": datetime.now().isoformat(),
                    "name": requirement.get("name"),
                    "plan": feature_result.get("plan"),
                    "agent_version": agent_version.version_id,
                    "status": "success",
                })
                self.save_feature_queue(queue)
                print(f"[Supervisor] Feature implemented: {requirement.get('name')}")
                return True
            else:
                print("[Supervisor] Tests failed after feature. Rolling back.")
                self.epoch_tracker.log_performance(agent_version.version_id, 0.0, status="failed")
                if branch_name:
                    self.git.rollback()
                    self.git.checkout_branch("main")
        else:
            print("[Supervisor] Feature files could not be applied.")
            self.epoch_tracker.log_performance(agent_version.version_id, 0.0, status="failed")
            if branch_name:
                self.git.checkout_branch("main")

        # Re-add the failed feature to queue front for retry
        queue.insert(0, requirement)
        self.save_feature_queue(queue)
        return False

    def run(self, interval=30):
        """
        Main loop: continuously check for bugs and features.
        Each iteration is treated as a new epoch in the EpochTracker.
        interval: seconds between cycles
        """
        print("[Supervisor] Evolution Supervisor started.")
        print(f"[Supervisor] Project root: {self.project_root}")
        print(f"[Supervisor] Cycle interval: {interval}s")

        while True:
            print(f"\n[{datetime.now().isoformat()}] === Running Evolution Cycle ===")

            # Start a new epoch for this cycle
            self.epoch_tracker.start_epoch()

            # Priority 1: Fix bugs
            fixed = self.process_bug_fix()
            if not fixed:
                # Priority 2: Implement features
                self.process_feature_request()

            # Persist epoch state and emit leaderboard
            self.epoch_tracker.save_checkpoint()
            self.epoch_tracker.print_leaderboard()

            # Generate a system-level summary report after every cycle
            self.reporter.generate_system_summary()

            print(f"[Supervisor] Sleeping {interval}s...")
            time.sleep(interval)


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    supervisor = Supervisor(root)
    supervisor.run()
