#!/usr/bin/env python3
"""
Ablation Study Results Analyzer

Analyzes results from all three baselines and produces:
- Comparative metrics tables
- Success rates by baseline
- Accuracy comparisons (for baselines 1 and 2 vs baseline 0)
- Exception frequency (for baseline 2)
- Charts and visualizations
"""

import json
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AblationAnalyzer:
    """Analyze ablation study results."""
    
    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or (PROJECT_ROOT / "logs" / "ablation")
        self.results_by_baseline = {}
        self.load_results()
    
    def load_results(self):
        """Load all transaction results from log directories."""
        for baseline in ["baseline0_full", "baseline1_no_comments", "baseline2_no_filtering"]:
            baseline_dir = self.log_dir / baseline
            
            if not baseline_dir.exists():
                continue
            
            # Look for transactions.json (from ablation_config metrics)
            tx_file = baseline_dir / "transactions.json"
            
            if tx_file.exists():
                try:
                    with open(tx_file, 'r') as f:
                        self.results_by_baseline[baseline] = json.load(f)
                except:
                    self.results_by_baseline[baseline] = []
            else:
                self.results_by_baseline[baseline] = []
    
    def compute_baseline_stats(self, baseline: str) -> Dict[str, Any]:
        """
        Compute statistics for a single baseline.
        
        Returns:
            Dictionary with:
            - total_transactions
            - successful_transactions
            - success_rate
            - avg_accuracy (if available)
            - avg_exceptions (for baseline2)
            - avg_decision_count
        """
        transactions = self.results_by_baseline.get(baseline, [])
        
        if not transactions:
            return {
                "baseline": baseline,
                "total_transactions": 0,
                "successful_transactions": 0,
                "success_rate": 0.0,
                "avg_accuracy": 0.0,
                "avg_exceptions": 0.0,
                "avg_decisions": 0.0,
                "avg_duration": 0.0
            }
        
        total = len(transactions)
        successful = sum(1 for tx in transactions if tx.get("success", False))
        success_rate = successful / total if total > 0 else 0.0
        
        # Accuracy (% valid message choices)
        accuracies = []
        for tx in transactions:
            if "accuracy_score" in tx:
                accuracies.append(tx["accuracy_score"])
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.0
        
        # Exception count (mainly for baseline2)
        exception_counts = [tx.get("exception_count", 0) for tx in transactions]
        avg_exceptions = sum(exception_counts) / len(exception_counts) if exception_counts else 0.0
        
        # Decision count
        decision_counts = [tx.get("total_decisions", 0) for tx in transactions]
        avg_decisions = sum(decision_counts) / len(decision_counts) if decision_counts else 0.0
        
        # Duration
        durations = [tx.get("duration_seconds", 0) for tx in transactions]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        return {
            "baseline": baseline,
            "total_transactions": total,
            "successful_transactions": successful,
            "success_rate": round(success_rate, 3),
            "avg_accuracy": round(avg_accuracy, 3),
            "avg_exceptions": round(avg_exceptions, 2),
            "avg_decisions": round(avg_decisions, 1),
            "avg_duration": round(avg_duration, 2),
            "transactions": transactions
        }
    
    def compute_comparative_metrics(self) -> Dict[str, Any]:
        """
        Compute comparative metrics across all baselines.
        
        Returns:
            Dictionary with baseline comparisons
        """
        baseline_stats = {}
        for baseline in ["baseline0_full", "baseline1_no_comments", "baseline2_no_filtering"]:
            if self.results_by_baseline.get(baseline):
                baseline_stats[baseline] = self.compute_baseline_stats(baseline)
        
        # Compute effects
        effects = {}
        
        if "baseline0_full" in baseline_stats and "baseline1_no_comments" in baseline_stats:
            full = baseline_stats["baseline0_full"]
            no_comments = baseline_stats["baseline1_no_comments"]
            
            accuracy_diff = no_comments["avg_accuracy"] - full["avg_accuracy"]
            success_diff = no_comments["success_rate"] - full["success_rate"]
            
            effects["effect_of_message_comments"] = {
                "description": "Impact of removing message comments",
                "accuracy_change": round(accuracy_diff, 3),
                "success_rate_change": round(success_diff, 3),
                "interpretation": self._interpret_effect(accuracy_diff, success_diff)
            }
        
        if "baseline0_full" in baseline_stats and "baseline2_no_filtering" in baseline_stats:
            full = baseline_stats["baseline0_full"]
            no_filtering = baseline_stats["baseline2_no_filtering"]
            
            accuracy_diff = no_filtering["avg_accuracy"] - full["avg_accuracy"]
            success_diff = no_filtering["success_rate"] - full["success_rate"]
            exception_avg = no_filtering["avg_exceptions"]
            
            effects["effect_of_enabled_filtering"] = {
                "description": "Impact of removing enabled set filtering (exception-driven learning)",
                "accuracy_change": round(accuracy_diff, 3),
                "success_rate_change": round(success_diff, 3),
                "avg_exceptions": round(exception_avg, 2),
                "interpretation": self._interpret_effect(accuracy_diff, success_diff, exception_avg)
            }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "baseline_statistics": baseline_stats,
            "comparative_effects": effects
        }
    
    def _interpret_effect(self, accuracy_diff: float, success_diff: float, exceptions: float = 0.0) -> str:
        """Interpret the magnitude and direction of an effect."""
        if accuracy_diff >= 0.1 and success_diff >= 0.1:
            return f"Strong positive effect (accuracy +{accuracy_diff:.1%}, success +{success_diff:.1%})"
        elif accuracy_diff <= -0.1 and success_diff <= -0.1:
            return f"Strong negative effect (accuracy {accuracy_diff:.1%}, success {success_diff:.1%})"
        elif abs(accuracy_diff) < 0.05 and abs(success_diff) < 0.05:
            return "Negligible effect"
        else:
            return f"Mixed effect (accuracy {accuracy_diff:+.1%}, success {success_diff:+.1%})"
    
    def generate_report(self) -> str:
        """Generate human-readable report of findings."""
        metrics = self.compute_comparative_metrics()
        
        lines = []
        lines.append("=" * 70)
        lines.append("ABLATION STUDY RESULTS")
        lines.append("=" * 70)
        lines.append(f"Generated: {metrics['timestamp']}\n")
        
        # Baseline statistics
        lines.append("BASELINE STATISTICS")
        lines.append("-" * 70)
        
        for baseline_name, stats in metrics.get("baseline_statistics", {}).items():
            lines.append(f"\n{baseline_name}:")
            lines.append(f"  Transactions:     {stats['total_transactions']} total, {stats['successful_transactions']} successful")
            lines.append(f"  Success Rate:     {stats['success_rate']:.1%}")
            lines.append(f"  Avg Accuracy:     {stats['avg_accuracy']:.1%}")
            lines.append(f"  Avg Exceptions:   {stats['avg_exceptions']:.1f}")
            lines.append(f"  Avg Decisions:    {stats['avg_decisions']:.1f}")
            lines.append(f"  Avg Duration:     {stats['avg_duration']:.1f}s")
        
        # Comparative effects
        lines.append("\n" + "=" * 70)
        lines.append("COMPARATIVE EFFECTS")
        lines.append("=" * 70)
        
        for effect_name, effect_data in metrics.get("comparative_effects", {}).items():
            lines.append(f"\n{effect_name}:")
            lines.append(f"  {effect_data['description']}")
            lines.append(f"  → Accuracy change:   {effect_data['accuracy_change']:+.1%}")
            lines.append(f"  → Success rate change: {effect_data['success_rate_change']:+.1%}")
            if "avg_exceptions" in effect_data:
                lines.append(f"  → Avg exceptions:     {effect_data['avg_exceptions']:.1f}")
            lines.append(f"  → Interpretation: {effect_data['interpretation']}")
        
        return "\n".join(lines)
    
    def save_report(self, output_file: Path = None):
        """Save report and metrics to JSON and text files."""
        output_file = output_file or (self.log_dir / "analysis_report.txt")
        metrics_file = self.log_dir / "analysis_metrics.json"
        
        # Generate and save report
        report = self.generate_report()
        with open(output_file, 'w') as f:
            f.write(report)
        
        print(f"Report saved to: {output_file}\n")
        
        # Save metrics JSON
        metrics = self.compute_comparative_metrics()
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print(f"Metrics saved to: {metrics_file}\n")
        
        # Print report to console
        print(report)


def main():
    analyzer = AblationAnalyzer()
    analyzer.save_report()


if __name__ == "__main__":
    main()
