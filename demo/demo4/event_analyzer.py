#!/usr/bin/env python3
"""
Event Analyzer: Post-execution analysis of custom events processing.

Analyzes:
1. How many events were injected vs. processed
2. Timeline of events relative to protocol messages
3. Correlation between events and agent decisions
4. LLM decision efficiency with external context

Produces a detailed JSON report for further analysis.
"""

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class EventAnalyzer:
    """Analyzes event processing from logs and metrics."""
    
    def __init__(self, log_file: Path, events_log_file: Optional[Path] = None):
        """
        Initialize the analyzer.
        
        Args:
            log_file: Path to agent execution log
            events_log_file: Optional path to events_log.json from simulator
        """
        self.log_file = log_file
        self.events_log_file = events_log_file
        self.results = {}
        
        # Parse log file
        self.log_lines = self._read_log_file()
        
        # Parse events log if provided
        self.injected_events = self._read_events_log()
    
    def _read_log_file(self) -> List[str]:
        """Read and parse the main agent log file."""
        try:
            with open(self.log_file, 'r') as f:
                return f.readlines()
        except Exception as e:
            print(f"Error reading log file: {e}")
            return []
    
    def _read_events_log(self) -> List[Dict[str, Any]]:
        """Read the events log from simulator."""
        if not self.events_log_file or not self.events_log_file.exists():
            return []
        
        try:
            with open(self.events_log_file, 'r') as f:
                data = json.load(f)
                return data.get("events", [])
        except Exception as e:
            print(f"Error reading events log: {e}")
            return []
    
    def extract_protocol_messages(self) -> List[Dict[str, Any]]:
        """Extract protocol messages from log."""
        messages = []
        
        for i, line in enumerate(self.log_lines):
            # Look for message patterns in logs
            if "Sending message:" in line or "Received message:" in line:
                try:
                    # Extract timestamp and message details
                    msg_dict = {
                        "line_number": i,
                        "raw_line": line.strip(),
                        "log_content": line
                    }
                    messages.append(msg_dict)
                except Exception:
                    pass
        
        return messages
    
    def extract_llm_decisions(self) -> List[Dict[str, Any]]:
        """Extract LLM decision points from log."""
        decisions = []
        
        for i, line in enumerate(self.log_lines):
            # Look for key decision indicators
            if "Consulting LLM for decision" in line:
                try:
                    decision_dict = {
                        "line_number": i,
                        "raw_line": line.strip(),
                        "event_context": ""
                    }
                    
                    # Check both directions for event context
                    # Look backwards first (events are logged before LLM decision)
                    for j in range(max(0, i - 20), i):
                        if "Loaded" in self.log_lines[j] and "event" in self.log_lines[j].lower():
                            # Check if we actually loaded events (not "Loaded 0 events")
                            if " 0 event" not in self.log_lines[j]:
                                decision_dict["event_context"] = "has_event_context"
                                break
                    
                    # Also look forward for explicit event context markers
                    if not decision_dict["event_context"]:
                        for j in range(i, min(i + 30, len(self.log_lines))):
                            if "=== PENDING EXTERNAL EVENTS ===" in self.log_lines[j]:
                                decision_dict["event_context"] = "has_event_context"
                                break
                            elif "Pending custom events:" in self.log_lines[j]:
                                decision_dict["event_context"] = "has_event_context"
                                break
                    
                    decisions.append(decision_dict)
                except Exception:
                    pass
        
        return decisions
    
    def extract_event_processing(self) -> List[Dict[str, Any]]:
        """Extract event processing from log."""
        events_processed = []
        
        for i, line in enumerate(self.log_lines):
            if "Pending custom events" in line or "Processing custom event" in line:
                events_processed.append({
                    "line_number": i,
                    "raw_line": line.strip()
                })
        
        return events_processed
    
    def analyze(self) -> Dict[str, Any]:
        """Perform full analysis of event processing."""
        self.results = {
            "analysis_timestamp": datetime.now().isoformat(),
            "log_file": str(self.log_file),
            "events_log_file": str(self.events_log_file) if self.events_log_file else None,
            
            # Event statistics
            "events_injected": len(self.injected_events),
            "injected_events": self.injected_events,
            
            # Protocol analysis
            "protocol_messages": self.extract_protocol_messages(),
            "message_count": len(self.extract_protocol_messages()),
            
            # LLM decision analysis
            "llm_decisions": self.extract_llm_decisions(),
            "llm_decision_count": len(self.extract_llm_decisions()),
            "llm_decisions_with_event_context": len([
                d for d in self.extract_llm_decisions() if d.get("event_context")
            ]),
            
            # Event processing
            "events_processed": self.extract_event_processing(),
            "events_processing_events_count": len(self.extract_event_processing()),
            
            # Summary
            "summary": self._generate_summary()
        }
        
        return self.results
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate analysis summary."""
        return {
            "total_protocol_messages": len(self.extract_protocol_messages()),
            "total_llm_decisions": len(self.extract_llm_decisions()),
            "external_event_injected": len(self.injected_events) > 0,
            "external_event_description": self.injected_events[0] if self.injected_events else None,
            "description": "Single external event (bat purchase) injected during protocol execution"
        }
    
    def save_report(self, output_file: Path):
        """Save the analysis report to JSON."""
        try:
            with open(output_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"Analysis report saved to {output_file}")
        except Exception as e:
            print(f"Error saving report: {e}")
    
    def print_summary(self):
        """Print a human-readable summary."""
        if not self.results:
            self.analyze()
        
        summary = self.results.get("summary", {})
        
        print("\n" + "="*60)
        print("DEMO 4: External Event Processing Analysis")
        print("="*60)
        print(f"External Event Injected:        {summary.get('external_event_injected', False)}")
        if summary.get('external_event_description'):
            event = summary['external_event_description']
            print(f"Event:                          {event.get('raw_line', 'Unknown')}")
        print(f"Protocol Messages Exchanged:    {summary.get('total_protocol_messages', 0)}")
        print(f"LLM Decision Points:            {summary.get('total_llm_decisions', 0)}")
        print("="*60 + "\n")


if __name__ == "__main__":
    # Test analyzer standalone
    if len(sys.argv) > 1:
        log_file = Path(sys.argv[1])
        events_log = Path(sys.argv[2]) if len(sys.argv) > 2 else None
        
        analyzer = EventAnalyzer(log_file, events_log)
        analyzer.analyze()
        analyzer.print_summary()
        
        # Save report
        report_file = log_file.parent / f"{log_file.stem}_event_analysis.json"
        analyzer.save_report(report_file)
