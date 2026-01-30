#!/usr/bin/env python3
"""
Base harness class for all experimental demonstrations.
Provides common tracing, logging, and reporting infrastructure.
"""

import asyncio
import json
import logging
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class DecisionEvent:
    """Records a rich decision point with full context."""
    
    def __init__(self, decision_id: str, protocol: str, role: str):
        self.decision_id = decision_id
        self.protocol = protocol
        self.role = role
        self.timestamp = datetime.now().isoformat()
        self.state_before: Optional[Dict[str, Any]] = None
        self.enabled_messages: List[str] = []
        self.llm_prompt: Optional[str] = None
        self.llm_response: Optional[Dict[str, Any]] = None
        self.selected_message_type: Optional[str] = None
        self.confidence_score: Optional[float] = None
        self.reasoning: Optional[str] = None
        self.state_after: Optional[Dict[str, Any]] = None
        self.execution_time_ms: Optional[float] = None
        self.consequences: List[Dict[str, Any]] = []
    
    def set_state_before(self, state: Dict[str, Any]) -> None:
        """Set the protocol state before decision."""
        self.state_before = state
    
    def set_enabled_messages(self, messages: List[str]) -> None:
        """Set available message options at decision point."""
        self.enabled_messages = messages
    
    def set_llm_context(self, prompt: str, response: Dict[str, Any]) -> None:
        """Set LLM prompt and response."""
        self.llm_prompt = prompt
        self.llm_response = response
    
    def set_decision(self, message_type: str, confidence: float = 1.0) -> None:
        """Set the decision made."""
        self.selected_message_type = message_type
        self.confidence_score = confidence
    
    def set_reasoning(self, reasoning: str) -> None:
        """Set human-readable reasoning for decision."""
        self.reasoning = reasoning
    
    def set_state_after(self, state: Dict[str, Any]) -> None:
        """Set the protocol state after decision."""
        self.state_after = state
    
    def set_execution_time(self, time_ms: float) -> None:
        """Set execution time in milliseconds."""
        self.execution_time_ms = time_ms
    
    def add_consequence(self, consequence_type: str, detail: str) -> None:
        """Record consequence of this decision."""
        self.consequences.append({
            "type": consequence_type,
            "detail": detail,
            "timestamp": datetime.now().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert decision event to JSON-serializable dict."""
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "protocol": self.protocol,
            "role": self.role,
            "state_before": self.state_before,
            "enabled_messages": self.enabled_messages,
            "llm_prompt": self.llm_prompt,
            "llm_response": self.llm_response,
            "selected_message_type": self.selected_message_type,
            "confidence_score": self.confidence_score,
            "reasoning": self.reasoning,
            "state_after": self.state_after,
            "execution_time_ms": self.execution_time_ms,
            "consequences": self.consequences
        }


class ExecutionTrace:
    """Records detailed execution trace for analysis."""
    
    def __init__(self, harness_name: str, scenario_id: str):
        self.harness_name = harness_name
        self.scenario_id = scenario_id
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.events: List[Dict[str, Any]] = []
        self.messages: List[Dict[str, Any]] = []
        self.states: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.decisions: List[DecisionEvent] = []
        self.metrics: Dict[str, Any] = {}
    
    def add_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Record an event."""
        self.events.append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        })
    
    def add_message(self, msg_type: str, sender: str, receiver: str, payload: Dict[str, Any]) -> None:
        """Record a protocol message."""
        self.messages.append({
            "timestamp": datetime.now().isoformat(),
            "type": msg_type,
            "sender": sender,
            "receiver": receiver,
            "payload": payload
        })
    
    def add_state_snapshot(self, protocol: str, role: str, state: Dict[str, Any]) -> None:
        """Record adapter state snapshot."""
        self.states.append({
            "timestamp": datetime.now().isoformat(),
            "protocol": protocol,
            "role": role,
            "state": state
        })
    
    def add_error(self, error_type: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Record an error/violation."""
        self.errors.append({
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": message,
            "context": context or {}
        })
    
    def add_decision(self, decision: DecisionEvent) -> None:
        """Record a rich decision event."""
        self.decisions.append(decision)
    
    def finalize(self) -> None:
        """Mark execution as complete."""
        self.end_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to JSON-serializable dict."""
        return {
            "harness": self.harness_name,
            "scenario_id": self.scenario_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else None,
            "events": self.events,
            "messages": self.messages,
            "states": self.states,
            "errors": self.errors,
            "decisions": [d.to_dict() for d in self.decisions],
            "metrics": self.metrics
        }
    
    def save_to_file(self, output_path: Path) -> None:
        """Save trace to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class BaseHarness(ABC):
    """Abstract base class for all experimental harnesses."""
    
    def __init__(self, harness_name: str, results_dir: Optional[Path] = None):
        self.harness_name = harness_name
        self.base_results_dir = results_dir or (PROJECT_ROOT / "demo" / "results")
        self.base_results_dir.mkdir(parents=True, exist_ok=True)
        
        # Create demo-specific results subfolder
        self.results_dir = self.base_results_dir / self.harness_name.replace(" ", "_").lower()
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging (logs still go to base results dir)
        self.logger = self._setup_logging()
        self.traces: List[ExecutionTrace] = []
    
    def _setup_logging(self) -> logging.Logger:
        """Configure logging for this harness."""
        logger = logging.getLogger(self.harness_name)
        logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        logger.handlers = []
        
        # File handler (in base results dir)
        log_file = self.base_results_dir / f"{self.harness_name}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    @abstractmethod
    async def run(self) -> Dict[str, Any]:
        """Run the harness and return results."""
        pass
    
    def create_trace(self, scenario_id: str) -> ExecutionTrace:
        """Create a new execution trace."""
        trace = ExecutionTrace(self.harness_name, scenario_id)
        self.traces.append(trace)
        return trace
    
    def save_raw_results(self, results: Dict[str, Any]) -> Path:
        """Save complete raw results to raw_results.json in demo subfolder."""
        output_path = self.results_dir / "raw_results.json"
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        self.logger.info(f"Saved raw results to {output_path}")
        return output_path
    
    def save_showcase_metrics(self, metrics: Dict[str, Any]) -> Path:
        """Save curated showcase metrics to showcase_metrics.json in demo subfolder."""
        output_path = self.results_dir / "showcase_metrics.json"
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        self.logger.info(f"Saved showcase metrics to {output_path}")
        return output_path
    
    def save_all_traces(self) -> None:
        """Save all execution traces to demo subfolder."""
        for i, trace in enumerate(self.traces):
            trace.finalize()
            output_path = self.results_dir / f"trace_{i}.json"
            trace.save_to_file(output_path)
            self.logger.info(f"Saved trace {i} to {output_path}")
    
    def generate_summary_report(self, results: Dict[str, Any]) -> str:
        """Generate a human-readable summary report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report = f"""
{'='*70}
{self.harness_name} - Execution Report
{'='*70}
Timestamp: {timestamp}
Status: {results.get('status', 'UNKNOWN')}
Results Directory: {self.results_dir}
{'='*70}

{json.dumps(results, indent=2)}

{'='*70}
"""
        return report
    
    def save_summary_report(self, results: Dict[str, Any]) -> None:
        """Save summary report to demo subfolder."""
        report = self.generate_summary_report(results)
        report_path = self.results_dir / "summary.txt"
        with open(report_path, 'w') as f:
            f.write(report)
        self.logger.info(f"Saved summary report to {report_path}")
    
    def log_info(self, msg: str) -> None:
        """Log info message."""
        self.logger.info(msg)
    
    def log_error(self, msg: str) -> None:
        """Log error message."""
        self.logger.error(msg)
    
    def log_debug(self, msg: str) -> None:
        """Log debug message."""
        self.logger.debug(msg)


__all__ = ['DecisionEvent', 'ExecutionTrace', 'BaseHarness']
