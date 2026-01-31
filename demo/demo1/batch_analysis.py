#!/usr/bin/env python3
"""
Batch Analysis: Aggregate multiple demo1 runs for comparative analysis
Useful for generating statistics and plots for papers/evaluation.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from statistics import mean, stdev
from datetime import datetime


def load_results_file(filepath: Path) -> Dict[str, Any]:
    """Load a single demo1 results JSON file."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {}


def find_all_demo_runs(results_dir: Path) -> List[Path]:
    """Find all demo1_*.json files in results directory."""
    return sorted([
        f for f in results_dir.glob("demo1_*.json")
        if "_analysis" not in f.name
    ])


def aggregate_metrics(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate metrics across multiple runs."""
    if not runs:
        return {}
    
    # Extract timing data
    execution_times = []
    llm_calls_list = []
    llm_durations = []
    
    for run in runs:
        metrics = run.get("metrics", [])
        for protocol_metric in metrics:
            execution_times.append(protocol_metric.get("execution_time", 0))
            llm_calls_list.append(protocol_metric.get("llm_call_count", 0))
            llm_durations.append(protocol_metric.get("llm_duration_seconds", 0))
    
    def safe_stdev(data):
        try:
            return round(stdev(data), 2) if len(data) > 1 else 0
        except:
            return 0
    
    return {
        "num_runs": len(runs),
        "total_protocols": sum(len(r.get("metrics", [])) for r in runs),
        "execution_time": {
            "mean_seconds": round(mean(execution_times), 2) if execution_times else 0,
            "stdev": safe_stdev(execution_times),
            "min_seconds": round(min(execution_times), 2) if execution_times else 0,
            "max_seconds": round(max(execution_times), 2) if execution_times else 0,
        },
        "llm_calls": {
            "mean_calls": round(mean(llm_calls_list), 1) if llm_calls_list else 0,
            "stdev": safe_stdev(llm_calls_list),
            "min_calls": min(llm_calls_list) if llm_calls_list else 0,
            "max_calls": max(llm_calls_list) if llm_calls_list else 0,
            "total_calls": sum(llm_calls_list),
        },
        "llm_duration": {
            "mean_seconds": round(mean(llm_durations), 2) if llm_durations else 0,
            "stdev": safe_stdev(llm_durations),
            "min_seconds": round(min(llm_durations), 2) if llm_durations else 0,
            "max_seconds": round(max(llm_durations), 2) if llm_durations else 0,
            "total_seconds": round(sum(llm_durations), 2),
        },
        "success_rate": {
            "successful_protocols": sum(
                1 for run in runs
                for m in run.get("metrics", [])
                if m.get("success", False)
            ),
            "total_protocols": sum(len(r.get("metrics", [])) for r in runs),
        }
    }


def analyze_batch(results_dir: Path) -> None:
    """Analyze all demo1 runs in results directory."""
    demo_runs = find_all_demo_runs(results_dir)
    
    if not demo_runs:
        print(f"No demo1 results found in {results_dir}")
        return
    
    print("\n" + "="*70)
    print("DEMO 1 BATCH ANALYSIS")
    print("="*70)
    print(f"\nResults Directory: {results_dir}")
    print(f"Runs Found: {len(demo_runs)}")
    
    runs = []
    for run_file in demo_runs:
        data = load_results_file(run_file)
        if data:
            runs.append(data)
            print(f"  ✓ {run_file.name}")
    
    if not runs:
        print("No valid results loaded")
        return
    
    # Aggregate metrics
    aggregated = aggregate_metrics(runs)
    
    print(f"\n" + "="*70)
    print("AGGREGATED METRICS")
    print("="*70)
    
    print(f"\nExecution Summary:")
    print(f"  Total Runs: {aggregated.get('num_runs', 0)}")
    print(f"  Total Protocols: {aggregated.get('total_protocols', 0)}")
    
    success = aggregated.get('success_rate', {})
    total = success.get('total_protocols', 1)
    successful = success.get('successful_protocols', 0)
    print(f"  Success Rate: {successful}/{total} ({(successful/total*100):.1f}%)" if total > 0 else "  Success Rate: N/A")
    
    print(f"\nExecution Time Statistics:")
    exec_time = aggregated.get('execution_time', {})
    print(f"  Mean: {exec_time.get('mean_seconds', 0)}s ± {exec_time.get('stdev', 0)}s")
    print(f"  Range: {exec_time.get('min_seconds', 0)}s - {exec_time.get('max_seconds', 0)}s")
    
    print(f"\nLLM Call Statistics:")
    llm_calls = aggregated.get('llm_calls', {})
    print(f"  Mean per Protocol: {llm_calls.get('mean_calls', 0)} ± {llm_calls.get('stdev', 0)}")
    print(f"  Range: {llm_calls.get('min_calls', 0)} - {llm_calls.get('max_calls', 0)}")
    print(f"  Total Calls: {llm_calls.get('total_calls', 0)}")
    
    print(f"\nLLM Duration Statistics:")
    llm_dur = aggregated.get('llm_duration', {})
    print(f"  Mean: {llm_dur.get('mean_seconds', 0)}s ± {llm_dur.get('stdev', 0)}s")
    print(f"  Range: {llm_dur.get('min_seconds', 0)}s - {llm_dur.get('max_seconds', 0)}s")
    print(f"  Total: {llm_dur.get('total_seconds', 0)}s")
    
    # Save batch analysis
    batch_analysis = {
        "timestamp": datetime.now().isoformat(),
        "num_runs": len(demo_runs),
        "runs_analyzed": [f.name for f in demo_runs],
        "aggregated_metrics": aggregated,
    }
    
    output_file = results_dir / f"batch_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(output_file, 'w') as f:
            json.dump(batch_analysis, f, indent=2)
        print(f"\n✓ Batch analysis saved to: {output_file}")
    except Exception as e:
        print(f"\n✗ Error saving batch analysis: {e}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    results_dir = Path(__file__).resolve().parent / "results"
    
    if len(sys.argv) > 1:
        results_dir = Path(sys.argv[1]).resolve()
    
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        sys.exit(1)
    
    analyze_batch(results_dir)
