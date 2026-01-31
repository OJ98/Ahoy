#!/usr/bin/env python3
"""
Demo 1 Analysis: Post-execution metrics aggregation
Reads demo results JSON and produces aggregate metrics and insights.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


def load_demo_results(results_file: Path) -> Optional[Dict[str, Any]]:
    """Load demo results from JSON file."""
    try:
        with open(results_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading results file: {e}")
        return None


def analyze_protocol_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze metrics for a single protocol."""
    return {
        "protocol": metrics.get("protocol_name", "Unknown"),
        "success": metrics.get("success", False),
        "execution_time_seconds": round(metrics.get("execution_time", 0), 2),
        "llm_calls": metrics.get("llm_call_count", 0),
        "llm_duration_seconds": round(metrics.get("llm_duration_seconds", 0), 2),
        "error": metrics.get("error_message", None),
    }


def analyze_demo1_results(results_file: Path) -> Dict[str, Any]:
    """
    Analyze demo results and produce aggregate metrics.
    
    Args:
        results_file: Path to demo results JSON file
        
    Returns:
        Dictionary with aggregate analysis results
    """
    results = load_demo_results(results_file)
    if not results:
        return {}
    
    metrics = results.get("metrics", [])
    
    # Protocol-level analysis
    protocol_analyses = [analyze_protocol_metrics(m) for m in metrics]
    
    # Aggregate metrics
    total_execution_time = sum(m.get("execution_time", 0) for m in metrics)
    total_llm_calls = sum(m.get("llm_call_count", 0) for m in metrics)
    total_llm_duration = sum(m.get("llm_duration_seconds", 0) for m in metrics)
    successful_protocols = sum(1 for m in metrics if m.get("success", False))
    total_protocols = len(metrics)
    
    analysis = {
        "demo_summary": {
            "run_timestamp": results.get("run_timestamp"),
            "total_protocols_executed": total_protocols,
            "protocols_successful": successful_protocols,
            "success_rate": f"{(successful_protocols / total_protocols * 100):.1f}%" if total_protocols > 0 else "N/A",
            "total_execution_time_seconds": round(total_execution_time, 2),
            "total_llm_calls": total_llm_calls,
            "total_llm_duration_seconds": round(total_llm_duration, 2),
            "average_llm_calls_per_protocol": round(total_llm_calls / total_protocols, 1) if total_protocols > 0 else 0,
            "average_execution_time_per_protocol": round(total_execution_time / total_protocols, 2) if total_protocols > 0 else 0,
        },
        "protocol_metrics": protocol_analyses,
    }
    
    return analysis


def print_analysis_report(analysis: Dict[str, Any]) -> None:
    """Print formatted analysis report."""
    if not analysis:
        print("No analysis data available")
        return
    
    summary = analysis.get("demo_summary", {})
    
    print("\n" + "="*70)
    print("DEMO 1 ANALYSIS REPORT")
    print("="*70)
    print(f"\nExecution Summary:")
    print(f"  Run Timestamp: {summary.get('run_timestamp', 'N/A')}")
    print(f"  Protocols Executed: {summary.get('total_protocols_executed', 0)}")
    print(f"  Successful: {summary.get('protocols_successful', 0)}/{summary.get('total_protocols_executed', 0)}")
    print(f"  Success Rate: {summary.get('success_rate', 'N/A')}")
    
    print(f"\nTiming Metrics:")
    print(f"  Total Execution Time: {summary.get('total_execution_time_seconds', 0)}s")
    print(f"  Avg per Protocol: {summary.get('average_execution_time_per_protocol', 0)}s")
    
    print(f"\nLLM Metrics:")
    print(f"  Total LLM Calls: {summary.get('total_llm_calls', 0)}")
    print(f"  Avg Calls per Protocol: {summary.get('average_llm_calls_per_protocol', 0)}")
    print(f"  Total LLM Duration: {summary.get('total_llm_duration_seconds', 0)}s")
    
    print(f"\nPer-Protocol Details:")
    for protocol in analysis.get("protocol_metrics", []):
        status = "SUCCESS" if protocol.get("success") else "FAILED"
        print(f"\n  {protocol.get('protocol')} [{status}]")
        print(f"    Execution Time: {protocol.get('execution_time_seconds')}s")
        print(f"    LLM Calls: {protocol.get('llm_calls')}")
        print(f"    LLM Duration: {protocol.get('llm_duration_seconds')}s")
        if protocol.get("error"):
            print(f"    Error: {protocol.get('error')}")
    
    print("\n" + "="*70)


def save_analysis_report(analysis: Dict[str, Any], output_file: Path) -> None:
    """Save analysis report to JSON file."""
    try:
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"Analysis report saved to: {output_file}")
    except Exception as e:
        print(f"Error saving analysis report: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python demo1_analysis.py <results_file>")
        sys.exit(1)
    
    results_file = Path(sys.argv[1])
    
    if not results_file.exists():
        print(f"Results file not found: {results_file}")
        sys.exit(1)
    
    analysis = analyze_demo1_results(results_file)
    print_analysis_report(analysis)
    
    # Save analysis report alongside results
    analysis_file = results_file.with_stem(results_file.stem + "_analysis")
    save_analysis_report(analysis, analysis_file)
