#!/usr/bin/env python3
"""
Ablation Study Configuration and Metrics Tracking

This module provides:
1. Baseline mode identification
2. Metrics collection and storage
3. Exception tracking
"""

import os
import json
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Baseline modes
class AblationMode(Enum):
    FULL = "baseline0_full"
    NO_COMMENTS = "baseline1_no_comments"
    NO_FILTERING = "baseline2_no_filtering"


def get_ablation_mode() -> AblationMode:
    """
    Detect current ablation mode from environment or code location.
    
    Priority:
    1. ABLATION_MODE environment variable
    2. Script location (if running from ablation/ subdir)
    3. Default to FULL
    """
    env_mode = os.getenv("ABLATION_MODE", "").lower()
    if env_mode:
        for mode in AblationMode:
            if mode.value in env_mode:
                return mode
    
    # Try to detect from __file__ location
    try:
        cwd = os.getcwd()
        if "baseline0_full" in cwd:
            return AblationMode.FULL
        elif "baseline1_no_comments" in cwd:
            return AblationMode.NO_COMMENTS
        elif "baseline2_no_filtering" in cwd:
            return AblationMode.NO_FILTERING
    except:
        pass
    
    return AblationMode.FULL


class AblationMetrics:
    """
    Track metrics for a single transaction in ablation study.
    """
    def __init__(self, baseline_mode: AblationMode, agent_name: str, protocol: str, role: str):
        self.baseline_mode = baseline_mode
        self.agent_name = agent_name
        self.protocol = protocol
        self.role = role
        self.start_time = datetime.now()
        
        # Message tracking
        self.messages_chosen = []  # List of (message_name, is_valid)
        self.messages_presented = 0  # Total options shown to LLM
        self.messages_enabled_count = 0  # Count of enabled messages (for comparison)
        self.accuracy_score = 0.0  # % of chosen messages that were valid
        
        # Exception tracking (mainly for baseline2)
        self.exceptions = []  # List of {type, message, recovery}
        self.exception_count = 0
        self.recovered_from_exception = 0
        
        # Transaction outcome
        self.success = False
        self.completion_message = None
        self.total_decisions = 0
        self.total_llm_calls = 0

    def record_message_choice(self, message_name: str, is_valid: bool):
        """Record that agent chose a message and whether it was valid."""
        self.messages_chosen.append((message_name, is_valid))
        if is_valid:
            self.accuracy_score = sum(1 for _, valid in self.messages_chosen if valid) / len(self.messages_chosen)
    
    def record_exception(self, exception_type: str, message: str, recovered: bool = False):
        """Record a kiko exception (mainly baseline2)."""
        self.exceptions.append({
            "type": exception_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "recovered": recovered
        })
        self.exception_count += 1
        if recovered:
            self.recovered_from_exception += 1
    
    def mark_success(self, completion_msg: str = None):
        """Mark transaction as successfully completed."""
        self.success = True
        self.completion_message = completion_msg
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize metrics to dictionary."""
        duration = (datetime.now() - self.start_time).total_seconds()
        return {
            "baseline_mode": self.baseline_mode.value,
            "agent_name": self.agent_name,
            "protocol": self.protocol,
            "role": self.role,
            "duration_seconds": duration,
            "success": self.success,
            "completion_message": self.completion_message,
            "total_decisions": self.total_decisions,
            "total_llm_calls": self.total_llm_calls,
            "messages_presented": self.messages_presented,
            "messages_enabled_count": self.messages_enabled_count,
            "messages_chosen": self.messages_chosen,
            "accuracy_score": round(self.accuracy_score, 3) if self.messages_chosen else 0.0,
            "exception_count": self.exception_count,
            "exceptions": self.exceptions,
            "recovered_from_exception": self.recovered_from_exception,
        }


class MetricsCollector:
    """
    Collect and store metrics for ablation study runs.
    """
    def __init__(self, log_dir: Optional[Path] = None):
        self.metrics: Dict[str, AblationMetrics] = {}
        self.log_dir = log_dir or (Path(__file__).parent.parent / "logs" / "ablation")
        self.baseline_mode = get_ablation_mode()
        self._ensure_log_dir()
    
    def _ensure_log_dir(self):
        """Create log directory if needed."""
        mode_dir = self.log_dir / self.baseline_mode.value
        mode_dir.mkdir(parents=True, exist_ok=True)
    
    def create_transaction_metrics(self, agent_name: str, protocol: str, role: str) -> AblationMetrics:
        """Create a new metrics tracker for a transaction."""
        tx_id = f"{agent_name}_{protocol}_{role}_{datetime.now().isoformat()}"
        metrics = AblationMetrics(self.baseline_mode, agent_name, protocol, role)
        self.metrics[tx_id] = metrics
        return metrics
    
    def save_metrics(self, tx_id: str, metrics: AblationMetrics):
        """Save metrics for a completed transaction."""
        mode_dir = self.log_dir / self.baseline_mode.value
        mode_dir.mkdir(parents=True, exist_ok=True)
        
        # Append to transactions.json
        tx_file = mode_dir / "transactions.json"
        transactions = []
        if tx_file.exists():
            try:
                with open(tx_file, 'r') as f:
                    transactions = json.load(f)
            except:
                transactions = []
        
        transactions.append(metrics.to_dict())
        
        with open(tx_file, 'w') as f:
            json.dump(transactions, f, indent=2)
    
    def get_mode(self) -> AblationMode:
        """Get current ablation mode."""
        return self.baseline_mode


# Global metrics collector (one per process)
_global_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector."""
    global _global_metrics_collector
    if _global_metrics_collector is None:
        _global_metrics_collector = MetricsCollector()
    return _global_metrics_collector
