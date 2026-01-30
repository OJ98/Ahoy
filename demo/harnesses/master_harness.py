#!/usr/bin/env python3
"""
Master Experimental Harness
Orchestrates all five demonstrations and generates unified report.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from demo.harnesses.demo1_protocol_portability import ProtocolPortabilityHarness
from demo.harnesses.demo2_guarantee_validation import GuaranteeValidationHarness
from demo.harnesses.demo3_concurrent_multiprotocol import ConcurrentMultiprotocolHarness
from demo.harnesses.demo4_decision_quality import DecisionQualityHarness
from demo.harnesses.demo5_protocol_selection import ProtocolSelectionHarness
from demo.harnesses.demo6_custom_events import CustomEventsHarness


class MasterHarness:
    """Orchestrates all experimental demonstrations."""
    
    def __init__(self):
        self.results_dir = PROJECT_ROOT / "demo" / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.start_time = datetime.now()
        self.demo_results = {}
    
    async def run_demo_1(self) -> Dict[str, Any]:
        """Run Demo 1: Protocol Portability."""
        print("\n" + "="*70)
        print("RUNNING DEMO 1: Protocol Portability")
        print("="*70)
        
        try:
            harness = ProtocolPortabilityHarness()
            results = await harness.run()
            return {
                "status": "completed",
                "results": results
            }
        except Exception as e:
            print(f"ERROR in Demo 1: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def run_demo_2(self) -> Dict[str, Any]:
        """Run Demo 2: Guarantee Validation."""
        print("\n" + "="*70)
        print("RUNNING DEMO 2: Guarantee Validation")
        print("="*70)
        
        try:
            harness = GuaranteeValidationHarness()
            results = await harness.run()
            return {
                "status": "completed",
                "results": results
            }
        except Exception as e:
            print(f"ERROR in Demo 2: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def run_demo_3(self) -> Dict[str, Any]:
        """Run Demo 3: Concurrent Multiprotocol Participation."""
        print("\n" + "="*70)
        print("RUNNING DEMO 3: Concurrent Multiprotocol Participation")
        print("="*70)
        
        try:
            harness = ConcurrentMultiprotocolHarness()
            results = await harness.run()
            return {
                "status": "completed",
                "results": results
            }
        except Exception as e:
            print(f"ERROR in Demo 3: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def run_demo_4(self) -> Dict[str, Any]:
        """Run Demo 4: Decision Quality Across Domains."""
        print("\n" + "="*70)
        print("RUNNING DEMO 4: Decision Quality Across Domains")
        print("="*70)
        
        try:
            harness = DecisionQualityHarness()
            results = await harness.run()
            return {
                "status": "completed",
                "results": results
            }
        except Exception as e:
            print(f"ERROR in Demo 4: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def run_demo_5(self) -> Dict[str, Any]:
        """Run Demo 5: Protocol Selection Accuracy."""
        print("\n" + "="*70)
        print("RUNNING DEMO 5: Protocol Selection Accuracy")
        print("="*70)
        
        try:
            harness = ProtocolSelectionHarness()
            results = await harness.run()
            return {
                "status": "completed",
                "results": results
            }
        except Exception as e:
            print(f"ERROR in Demo 5: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def run_demo_6(self) -> Dict[str, Any]:
        """Run Demo 6: Custom LLM Events."""
        print("\n" + "="*70)
        print("RUNNING DEMO 6: Custom LLM Events")
        print("="*70)
        
        try:
            harness = CustomEventsHarness()
            results = await harness.run_all_scenarios()
            return {
                "status": "completed",
                "results": results
            }
        except Exception as e:
            print(f"ERROR in Demo 6: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def run_all(self, skip_demos: list = None) -> Dict[str, Any]:
        """
        Run all demonstrations.
        
        Args:
            skip_demos: List of demo numbers to skip (e.g., [1, 3])
        """
        if skip_demos is None:
            skip_demos = []
        
        print("\n" + "="*70)
        print("AHOY EXPERIMENTAL DEMONSTRATION SUITE")
        print("="*70)
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Results directory: {self.results_dir}")
        print("="*70)
        
        # Run demonstrations
        demo_runners = {
            1: self.run_demo_1,
            2: self.run_demo_2,
            3: self.run_demo_3,
            4: self.run_demo_4,
            5: self.run_demo_5,
            6: self.run_demo_6,
        }
        
        for demo_num in sorted(demo_runners.keys()):
            if demo_num in skip_demos:
                print(f"\nSkipping Demo {demo_num}")
                self.demo_results[f"demo{demo_num}"] = {"status": "skipped"}
                continue
            
            result = await demo_runners[demo_num]()
            self.demo_results[f"demo{demo_num}"] = result
        
        # Generate unified report
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        unified_report = {
            "experiment_suite": "ahoy_demonstrations",
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "results_directory": str(self.results_dir),
            "demonstrations": self.demo_results,
            "summary": self._generate_summary()
        }
        
        # Save unified report
        report_path = self.results_dir / "master_report.json"
        with open(report_path, 'w') as f:
            json.dump(unified_report, f, indent=2)
        
        print("\n" + "="*70)
        print("EXPERIMENT SUITE COMPLETE")
        print("="*70)
        print(f"Ended: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Master report saved to: {report_path}")
        print("="*70)
        
        return unified_report
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics across all demos."""
        summary = {
            "demos_completed": 0,
            "demos_failed": 0,
            "demos_skipped": 0,
            "demo_statuses": {}
        }
        
        for demo_name, demo_result in self.demo_results.items():
            status = demo_result.get("status", "unknown")
            summary["demo_statuses"][demo_name] = status
            
            if status == "completed":
                summary["demos_completed"] += 1
            elif status == "error":
                summary["demos_failed"] += 1
            elif status == "skipped":
                summary["demos_skipped"] += 1
        
        return summary


async def main():
    """Run the master experimental harness."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AHOY Experimental Demonstration Suite")
    parser.add_argument(
        "--skip",
        type=int,
        nargs='+',
        default=[],
        help="Demo numbers to skip (e.g., --skip 1 3)"
    )
    parser.add_argument(
        "--only",
        type=int,
        nargs='+',
        default=None,
        help="Run only specific demos (e.g., --only 1 5 6)"
    )
    
    args = parser.parse_args()
    
    harness = MasterHarness()
    
    # Determine which demos to skip
    skip_demos = args.skip
    if args.only:
        skip_demos = [i for i in range(1, 7) if i not in args.only]
    
    results = await harness.run_all(skip_demos=skip_demos)
    
    # Print summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(json.dumps(results['summary'], indent=2))
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
