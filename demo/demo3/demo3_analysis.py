#!/usr/bin/env python3
"""
Demo 3 Analysis: Post-execution analysis for concurrent multiprotocol runs.
Analyzes metrics from simultaneous Protocol execution and generates insights.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def load_metrics(metrics_file: str) -> Dict[str, Any]:
    """Load metrics from JSON file."""
    try:
        with open(metrics_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading metrics: {e}")
        return {}


def analyze_concurrent_execution(metrics_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze concurrent multiprotocol execution metrics.
    """
    if not metrics_data.get("metrics"):
        return {}
    
    metrics = metrics_data["metrics"]
    
    # Calculate aggregates
    total_execution_time = max(m.get("execution_time", 0) for m in metrics) if metrics else 0
    total_llm_calls = sum(m.get("llm_call_count", 0) for m in metrics)
    total_llm_duration = sum(m.get("llm_duration_seconds", 0) for m in metrics)
    time_saved = total_llm_duration - total_execution_time if total_execution_time > 0 else 0
    success_count = sum(1 for m in metrics if m.get("success", False))
    
    # Per-protocol analysis
    protocol_analysis = {}
    for metric in metrics:
        protocol = metric.get("protocol_name", "Unknown")
        protocol_analysis[protocol] = {
            "role": metric.get("role_name"),
            "execution_time": metric.get("execution_time", 0),
            "llm_calls": metric.get("llm_call_count", 0),
            "llm_duration": metric.get("llm_duration_seconds", 0),
            "success": metric.get("success", False),
            "efficiency": (metric.get("llm_call_count", 0) / total_llm_calls * 100) if total_llm_calls > 0 else 0
        }
    
    # Parallel efficiency metrics
    sequential_time = total_llm_duration
    concurrent_time = total_execution_time
    speedup = sequential_time / concurrent_time if concurrent_time > 0 else 1
    efficiency = (speedup / len(metrics)) * 100 if len(metrics) > 0 else 0
    
    return {
        "run_timestamp": metrics_data.get("run_timestamp", ""),
        "execution_mode": "concurrent",
        "protocols_executed": len(metrics),
        "protocols_successful": success_count,
        "total_execution_time_seconds": round(total_execution_time, 2),
        "total_llm_calls": total_llm_calls,
        "total_llm_duration_seconds": round(total_llm_duration, 2),
        "time_saved_vs_sequential_seconds": round(time_saved, 2),
        "speedup_factor": round(speedup, 2),
        "parallel_efficiency_percent": round(efficiency, 1),
        "per_protocol_metrics": protocol_analysis,
        "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def print_analysis_report(analysis: Dict[str, Any]) -> None:
    """Print formatted analysis report."""
    if not analysis:
        print("No analysis data available")
        return
    
    print("\n" + "="*70)
    print("DEMO 3 CONCURRENT MULTIPROTOCOL ANALYSIS REPORT")
    print("="*70 + "\n")
    
    print(f"Run Timestamp: {analysis.get('run_timestamp', 'N/A')}")
    print(f"Execution Mode: {analysis.get('execution_mode', 'N/A')}")
    print(f"Analysis Time: {analysis.get('analysis_timestamp', 'N/A')}\n")
    
    print(f"Protocols Executed: {analysis['protocols_executed']}")
    print(f"Protocols Successful: {analysis['protocols_successful']}/{analysis['protocols_executed']}")
    print(f"Success Rate: {(analysis['protocols_successful'] / analysis['protocols_executed'] * 100):.1f}%\n")
    
    print("EXECUTION PERFORMANCE:")
    print("-" * 70)
    print(f"Total Execution Time (actual concurrent): {analysis['total_execution_time_seconds']:.2f}s")
    print(f"Total LLM Duration (sum sequential):      {analysis['total_llm_duration_seconds']:.2f}s")
    print(f"Time Saved (vs running sequentially):     {analysis['time_saved_vs_sequential_seconds']:.2f}s")
    print(f"Speedup Factor:                           {analysis['speedup_factor']:.2f}x")
    print(f"Parallel Efficiency:                      {analysis['parallel_efficiency_percent']:.1f}%\n")
    
    print("LLM METRICS:")
    print("-" * 70)
    print(f"Total LLM Calls: {analysis['total_llm_calls']}")
    print(f"Average Calls per Protocol: {(analysis['total_llm_calls'] / analysis['protocols_executed']):.1f}")
    print(f"Average LLM Duration: {(analysis['total_llm_duration_seconds'] / analysis['protocols_executed']):.2f}s\n")
    
    print("PER-PROTOCOL DETAILS:")
    print("-" * 70)
    for protocol_name, metrics in analysis.get('per_protocol_metrics', {}).items():
        status = "[SUCCESS]" if metrics['success'] else "[FAILED]"
        print(f"\n{protocol_name} ({metrics['role']}) - {status}")
        print(f"  Execution Time:  {metrics['execution_time']:.2f}s")
        print(f"  LLM Calls:       {metrics['llm_calls']}")
        print(f"  LLM Duration:    {metrics['llm_duration']:.2f}s")
        print(f"  Call Distribution: {metrics['efficiency']:.1f}% of total calls")
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70 + "\n")


def save_analysis_report(analysis: Dict[str, Any], output_file: Path) -> None:
    """Save analysis report to JSON file."""
    try:
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"Analysis report saved to: {output_file}")
    except Exception as e:
        print(f"Error saving analysis report: {e}")


def main():
    """Main analysis entry point."""
    if len(sys.argv) < 2:
        print("Usage: python demo3_analysis.py <metrics_file>")
        sys.exit(1)
    
    metrics_file = sys.argv[1]
    metrics_data = load_metrics(metrics_file)
    
    if not metrics_data:
        print("No metrics data found")
        sys.exit(1)
    
    # Analyze
    analysis = analyze_concurrent_execution(metrics_data)
    
    # Print report
    print_analysis_report(analysis)
    
    # Save report
    if metrics_file:
        output_file = Path(metrics_file).parent / f"demo3_{analysis['run_timestamp']}_analysis.json"
        save_analysis_report(analysis, output_file)


if __name__ == "__main__":
    main()
