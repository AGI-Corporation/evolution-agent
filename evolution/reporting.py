# evolution/reporting.py
# Extensive reporting and tracking for self-evolving agent systems.
# Provides analytics on mutations, success rates, and lineage performance.

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class EvolutionReporter:
    """
    Handles extensive reporting and historical tracking of the evolution process.
    Generates reports on agent performance, mutation trends, and system health.
    """

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.reports_dir = os.path.join(project_root, "logs", "reports")
        self.memory_path = os.path.join(project_root, "evolution", "memory.json")
        self.epoch_log_path = os.path.join(project_root, "evolution", "epoch_log.json")
        
        os.makedirs(self.reports_dir, exist_ok=True)

    def generate_epoch_report(self, epoch_id: int) -> Dict[str, Any]:
        """Generate a detailed report for a specific epoch."""
        try:
            with open(self.epoch_log_path, "r") as f:
                data = json.load(f)
            
            # If requesting current epoch or specific history
            # Filter history for the specific epoch
            epoch_history = [entry for entry in data.get("history", []) if entry.get("epoch") == epoch_id]
            
            if not epoch_history:
                return {"error": f"No data found for epoch {epoch_id}"}

            total_agents = len(epoch_history)
            successful_tests = len([a for a in epoch_history if a.get("status") == "tested"])
            failed_tests = len([a for a in epoch_history if a.get("status") == "failed"])
            avg_fitness = sum(a.get("fitness_score", 0) for a in epoch_history) / total_agents if total_agents > 0 else 0
            
            report = {
                "epoch": epoch_id,
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "total_agents": total_agents,
                    "success_rate": successful_tests / total_agents if total_agents > 0 else 0,
                    "failure_rate": failed_tests / total_agents if total_agents > 0 else 0,
                    "average_fitness": avg_fitness,
                    "peak_fitness": max(a.get("fitness_score", 0) for a in epoch_history) if epoch_history else 0
                },
                "top_agents": sorted(epoch_history, key=lambda x: x.get("fitness_score", 0), reverse=True)[:3]
            }

            self._save_report(f"epoch_{epoch_id}_report.json", report)
            return report

        except Exception as e:
            logger.error(f"Error generating epoch report: {e}")
            return {"error": str(e)}

    def generate_system_summary(self) -> Dict[str, Any]:
        """Generate a high-level summary of the entire evolution system."""
        try:
            if not os.path.exists(self.memory_path):
                return {"error": "Memory file not found"}

            with open(self.memory_path, "r") as f:
                memory_data = json.load(f)

            bug_fixes = [m for m in memory_data if m.get("type") == "bug_fix"]
            features = [m for m in memory_data if m.get("type") == "feature"]
            epochs = [m for m in memory_data if m.get("type") == "epoch_checkpoint"]

            summary = {
                "system_status": "active",
                "total_cycles": len(memory_data),
                "evolution_metrics": {
                    "total_epochs": len(epochs),
                    "total_bug_fixes": len(bug_fixes),
                    "total_features": len(features),
                    "uptime_since": memory_data[0].get("timestamp") if memory_data else "N/A"
                },
                "recent_activity": memory_data[-10:] # Last 10 events
            }

            self._save_report("system_summary.json", summary)
            return summary

        except Exception as e:
            logger.error(f"Error generating system summary: {e}")
            return {"error": str(e)}

    def _save_report(self, filename: str, content: Dict[str, Any]):
        """Internal helper to save report to disk."""
        path = os.path.join(self.reports_dir, filename)
        with open(path, "w") as f:
            json.dump(content, f, indent=4)
        logger.info(f"Report saved to {path}")

# Example usage for CLI reporting
if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    reporter = EvolutionReporter(root)
    print(json.dumps(reporter.generate_system_summary(), indent=2))
