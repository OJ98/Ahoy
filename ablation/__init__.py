#!/usr/bin/env python3
"""
Ablation study package for AHOY multi-agent system.

This package contains three baseline variants to isolate the value of:
1. Message comments from BSPL protocol definitions
2. Enabled set filtering (protocol constraint satisfaction)

Baselines:
- baseline0_full: Full AHOY with comments and enabled filtering (reference)
- baseline1_no_comments: Comments removed, enabled filtering kept
- baseline2_no_filtering: All messages shown, learning via exceptions

Usage:
    from ablation.ablation_config import get_ablation_mode, get_metrics_collector
    
    mode = get_ablation_mode()  # Detect current baseline
    metrics = get_metrics_collector()  # Track metrics
"""

__version__ = "1.0"
__all__ = ["ablation_config", "run_ablation", "analyze_results"]
