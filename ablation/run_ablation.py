#!/usr/bin/env python3
"""
Ablation Study Orchestration Harness

Runs all three baselines (or selected ones) on specified protocols
and collects metrics for comparison.

Usage:
    python run_ablation.py --baselines baseline0_full baseline1_no_comments --protocols Purchase --runs 3
    python run_ablation.py --all --runs 2
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import json
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ABLATION_DIR = PROJECT_ROOT / "ablation"
BASELINES = ["baseline0_full", "baseline1_no_comments", "baseline2_no_filtering"]
PROTOCOLS = ["Purchase", "Logistics", "Flexible_Purchase", "Credit_Purchase", "NetBill"]

# Add project root to path for imports
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.ui_manager import UserInterface


class AblationHarness:
    """Orchestrate ablation study runs."""
    
    def __init__(self):
        self.ui = UserInterface()
        self.log_dir = PROJECT_ROOT / "logs" / "ablation"
        self.results = {}
        self._verify_environment()
    
    def _verify_environment(self):
        """Verify that maf-py conda environment is active."""
        import subprocess
        
        # Check if maf-py is in the Python executable path
        if "maf-py" not in sys.executable and "maf-py" not in sys.prefix:
            self.ui.error(
                "ERROR: maf-py conda environment is NOT active!\n"
                "Please activate it with: conda activate maf-py\n"
                "Then run this script again."
            )
            raise SystemExit("Ablation harness requires maf-py conda environment")
        
        self.ui.message(f"✓ Environment verified: {sys.executable}\n")
    
    def _setup_logging(self):
        """Create ablation logging directory."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        for baseline in BASELINES:
            (self.log_dir / baseline).mkdir(parents=True, exist_ok=True)
    
    def run_single_baseline_transaction(
        self,
        baseline: str,
        protocol: str,
        role: str,
        run_num: int
    ) -> Dict:
        """
        Run a single transaction for a baseline.
        
        Returns:
            Dictionary with run results {success, error, metrics_file}
        """
        baseline_dir = ABLATION_DIR / baseline
        agent_script = baseline_dir / "ahoy.py"
        
        if not agent_script.exists():
            return {
                "success": False,
                "error": f"Agent script not found: {agent_script}",
                "metrics_file": None
            }
        
        self.ui.message(f"\n[RUN {run_num}] {baseline} → {protocol}:{role}")
        
        # Set up environment
        env = os.environ.copy()
        env["ABLATION_MODE"] = baseline
        env["ABLATION_PROTOCOL"] = protocol
        env["ABLATION_ROLE"] = role
        
        # Log file for this run
        log_file = self.log_dir / baseline / f"{protocol}_{role}_run{run_num}.log"
        
        try:
            # Run the agent using the current Python executable (which should be in maf-py)
            with open(log_file, 'w') as logf:
                result = subprocess.run(
                    [sys.executable, str(agent_script)],
                    cwd=str(PROJECT_ROOT),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout per transaction
                )
            
            # Log output
            with open(log_file, 'a') as logf:
                logf.write("=== STDOUT ===\n")
                logf.write(result.stdout)
                logf.write("\n=== STDERR ===\n")
                logf.write(result.stderr)
                logf.write(f"\n=== EXIT CODE ===\n{result.returncode}\n")
            
            success = result.returncode == 0
            
            if success:
                self.ui.success(f"✓ Completed")
            else:
                self.ui.error(f"✗ Failed (exit code {result.returncode})")
            
            return {
                "success": success,
                "error": None if success else result.stderr[:200],
                "metrics_file": str(log_file),
                "exit_code": result.returncode
            }
        
        except subprocess.TimeoutExpired:
            self.ui.error("✗ Timeout (5 minutes exceeded)")
            return {
                "success": False,
                "error": "Transaction timeout (5 minutes)",
                "metrics_file": str(log_file)
            }
        
        except Exception as e:
            self.ui.error(f"✗ Exception: {e}")
            return {
                "success": False,
                "error": str(e),
                "metrics_file": str(log_file)
            }
    
    def run_baseline_protocol(
        self,
        baseline: str,
        protocol: str,
        num_runs: int
    ):
        """
        Run multiple transactions for a baseline on a protocol.
        """
        self.ui.divider()
        self.ui.header(f"Baseline: {baseline}")
        self.ui.header(f"Protocol: {protocol}")
        self.ui.header(f"Runs: {num_runs}")
        self.ui.divider()
        
        # For now, use a simple role from each protocol
        # In future, could enumerate all roles
        role_map = {
            "Purchase": "Buyer",
            "Logistics": "Wrapper",
            "Flexible_Purchase": "FlexibleCustomer",
            "Credit_Purchase": "CreditCustomer",
            "NetBill": "NetBillCustomer"
        }
        
        role = role_map.get(protocol, "Buyer")
        
        # Run multiple transactions
        results = []
        for run_num in range(1, num_runs + 1):
            result = self.run_single_baseline_transaction(
                baseline, protocol, role, run_num
            )
            results.append(result)
        
        return results
    
    def run_all(
        self,
        baselines: List[str],
        protocols: List[str],
        num_runs: int
    ):
        """
        Run the complete ablation study.
        """
        self.ui.message("\n" + "=" * 70)
        self.ui.message("ABLATION STUDY - Multi-Baseline Comparison")
        self.ui.message("=" * 70)
        self.ui.message(f"Baselines: {', '.join(baselines)}")
        self.ui.message(f"Protocols: {', '.join(protocols)}")
        self.ui.message(f"Runs per protocol: {num_runs}")
        self.ui.message("=" * 70 + "\n")
        
        # Setup
        self._setup_logging()
        
        # Run all combinations
        total_runs = len(baselines) * len(protocols) * num_runs
        current_run = 0
        
        for baseline in baselines:
            for protocol in protocols:
                current_run += 1
                self.ui.message(f"\n[{current_run}/{total_runs}] Starting {baseline} on {protocol}...\n")
                
                results = self.run_baseline_protocol(baseline, protocol, num_runs)
                
                if baseline not in self.results:
                    self.results[baseline] = {}
                self.results[baseline][protocol] = results
        
        # Save summary
        self._save_summary()
        
        self.ui.divider()
        self.ui.message("Ablation study complete!")
        self.ui.message(f"Results saved to: {self.log_dir}")
    
    def _save_summary(self):
        """Save summary of all results."""
        summary_file = self.log_dir / "summary.json"
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "results": self.results,
            "baselines": list(self.results.keys()),
            "total_runs": sum(
                len(protocol_results) 
                for baseline_results in self.results.values()
                for protocol_results in baseline_results.values()
            )
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.ui.message(f"\nSummary saved to: {summary_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Run AHOY ablation study with multiple baselines"
    )
    
    parser.add_argument(
        "--baselines",
        nargs="+",
        choices=BASELINES,
        help="Baselines to run (default: all)"
    )
    
    parser.add_argument(
        "--protocols",
        nargs="+",
        choices=PROTOCOLS,
        help="Protocols to test (default: Purchase, Logistics)"
    )
    
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per baseline/protocol (default: 3)"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all baselines and all protocols"
    )
    
    args = parser.parse_args()
    
    # Determine baselines
    baselines = args.baselines if args.baselines else BASELINES
    
    # Determine protocols
    protocols = args.protocols if args.protocols else ["Purchase", "Logistics"]
    
    # Run harness
    harness = AblationHarness()
    harness.run_all(baselines, protocols, args.runs)


if __name__ == "__main__":
    main()
