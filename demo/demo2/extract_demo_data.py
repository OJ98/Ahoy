#!/usr/bin/env python3
"""
Extract structured demo data from CHiPs-Ahoy execution logs.

Takes a debug log file and extracts decision-event sequences:
- Event trigger (InitEvent, message received, etc.)
- Message history at that decision point
- Available options
- LLM reasoning and choice
- Message sent with parameters

Output: JSON file with decision-event sequence for paper results sections.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class MessageInHistory:
    """A single message as shown in the LLM's message history."""
    number: int
    message_type: str
    sender: str
    receiver: str
    parameters: Dict[str, str]
    protocol: Optional[str] = None


@dataclass
class Option:
    """An available option shown to the LLM."""
    option_number: int
    message_type: str
    missing_params: List[str]
    bound_params: Dict[str, str] = field(default_factory=dict)


@dataclass
class DecisionEvent:
    """A single LLM decision point."""
    decision_number: int
    event_type: str  # InitEvent, message received, enabled change, etc.
    message_history: List[MessageInHistory]
    available_options: List[Option]
    llm_reasoning: str
    llm_choice: Optional[int]  # which option was chosen (None if declined all)
    llm_choice_params: Dict[str, str] = field(default_factory=dict)
    message_sent: Optional[str] = None  # message type that was sent


@dataclass
class ParameterBinding:
    """Represents a parameter and its binding across protocols."""
    name: str
    protocol: str
    values: List[str]


@dataclass
class DemoMetrics:
    """Aggregated metrics for a demo run."""
    total_decision_events: int
    protocol_count: int
    protocols: List[str]
    roles: List[Tuple[str, str]]  # [(protocol, role)]
    violations: int
    exceptions: int
    elapsed_time_seconds: Optional[float]
    completion_rules: Dict[str, str]  # protocol_role -> rule


@dataclass
class DemoData:
    """Complete extracted data for a demo."""
    decision_events: List[DecisionEvent]
    parameters: Dict[str, ParameterBinding]
    metrics: DemoMetrics
    status: str  # "success", "partial", "error"
    extraction_timestamp: str


class ProtocolLogExtractor:
    """Extract structured decision-event data from CHiPs-Ahoy debug logs."""

    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self.lines = self._read_log()
        self.demo_data = DemoData(
            decision_events=[],
            parameters={},
            metrics=DemoMetrics(
                total_decision_events=0,
                protocol_count=0,
                protocols=[],
                roles=[],
                violations=0,
                exceptions=0,
                elapsed_time_seconds=None,
                completion_rules={}
            ),
            status="success",
            extraction_timestamp=datetime.now().isoformat()
        )

    def _read_log(self) -> List[str]:
        """Read log file into memory."""
        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.readlines()
        except FileNotFoundError:
            print(f"Error: Log file not found at {self.log_path}")
            sys.exit(1)

    def extract_all(self) -> DemoData:
        """Main extraction pipeline."""
        self._extract_decision_events()
        self._extract_parameters_from_events()
        self._extract_metrics()
        self._extract_completion_rules()
        return self.demo_data

    def _extract_decision_events(self) -> None:
        """Extract decision events and their associated context."""
        decision_number = 0
        i = 0
        
        while i < len(self.lines):
            line = self.lines[i]
            
            # Look for decision point indicator
            if "USER PROMPT FOR MESSAGE CHOICE (Decision #" in line:
                decision_number += 1
                
                # Extract decision number from line
                match = re.search(r'Decision #(\d+)', line)
                decision_num = int(match.group(1)) if match else decision_number
                
                # Find the event type before this decision
                event_type = self._find_event_type(i)
                
                # Extract message history for this decision
                i, history = self._extract_history_section(i)
                
                # Extract options
                i, options = self._extract_options_section(i)
                
                # Skip to raw LLM response and extract full reasoning
                reasoning = ""
                while i < len(self.lines):
                    if "RAW LLM RESPONSE" in self.lines[i]:
                        i += 1
                        # Skip the ====== line
                        while i < len(self.lines) and "=" in self.lines[i]:
                            i += 1
                        # Extract reasoning until we hit the next separator or parsed response
                        reasoning_lines = []
                        while i < len(self.lines):
                            line = self.lines[i]
                            # Stop at the next major section
                            if "PARSED LLM RESPONSE" in line or ("====" in line and len(reasoning_lines) > 5):
                                break
                            # Remove timestamp prefixes if present
                            clean_line = re.sub(r'^\d{4}-\d{2}-\d{2}.*? - DEBUG - ', '', line.strip())
                            if clean_line:
                                reasoning_lines.append(clean_line)
                            i += 1
                        reasoning = "\n".join(reasoning_lines[:30]).strip()  # First 30 lines
                        break
                    i += 1
                
                # Find what was actually chosen and sent
                choice_num, choice_params, message_sent = self._find_choice_result(i)
                
                event = DecisionEvent(
                    decision_number=decision_num,
                    event_type=event_type,
                    message_history=history,
                    available_options=options,
                    llm_reasoning=reasoning,
                    llm_choice=choice_num,
                    llm_choice_params=choice_params,
                    message_sent=message_sent
                )
                
                self.demo_data.decision_events.append(event)
            
            i += 1

    def _find_event_type(self, search_start: int) -> str:
        """Look backward from decision point to find event type."""
        for i in range(search_start - 1, max(0, search_start - 50), -1):
            line = self.lines[i]
            if "InitEvent" in line:
                return "InitEvent"
            if "message received" in line.lower():
                return "Message Received"
            if "enabled message" in line.lower() or "enabled set" in line.lower():
                return "Enabled Set Changed"
        return "Unknown"

    def _extract_history_section(self, search_start: int) -> Tuple[int, List[MessageInHistory]]:
        """Extract message history from the decision point."""
        history = []
        i = search_start
        in_history = False
        
        while i < len(self.lines):
            line = self.lines[i]
            
            if "=== MESSAGE HISTORY ===" in line:
                in_history = True
                i += 1
                continue
            
            if in_history and "END HISTORY" in line:
                return i, history
            
            if not in_history:
                i += 1
                continue
            
            # Parse message line: "NUMBER. message_type (from Role to Role)"
            stripped = line.strip()
            if not stripped or stripped.startswith("No message") or stripped.startswith("==="):
                i += 1
                continue
            
            match = re.match(
                r'^(\d+)\.\s+(\w+)\s*\(from\s+(\w+)\s+to\s+(\w+)\)',
                stripped
            )
            if match:
                msg_num = int(match.group(1))
                msg_type = match.group(2)
                sender = match.group(3)
                receiver = match.group(4)
                
                # Look ahead for parameters
                params = {}
                for j in range(i + 1, min(i + 10, len(self.lines))):
                    param_line = self.lines[j].strip()
                    
                    # Stop at next message, Options marker, or section marker
                    if re.match(r'^\d+\.', param_line) or "Options:" in param_line or "===" in param_line:
                        break  # Next message or section
                    
                    # Only extract valid param lines: "KEY: value" (skip option definitions)
                    if ':' in param_line and not param_line.startswith('[') and not param_line.startswith('0)'):
                        key, value = param_line.split(':', 1)
                        params[key.strip()] = value.strip()
                
                msg = MessageInHistory(
                    number=msg_num,
                    message_type=msg_type,
                    sender=sender,
                    receiver=receiver,
                    parameters=params
                )
                history.append(msg)
            
            i += 1
        
        return i, history

    def _extract_options_section(self, search_start: int) -> Tuple[int, List[Option]]:
        """Extract available options shown to LLM."""
        options = []
        i = search_start
        in_options = False
        
        while i < len(self.lines):
            line = self.lines[i]
            
            if "Options:" in line:
                in_options = True
                i += 1
                continue
            
            if in_options and ("Response format" in line or "Examples:" in line):
                return i, options
            
            if not in_options:
                i += 1
                continue
            
            stripped = line.strip()
            if not stripped:
                i += 1
                continue
            
            # Parse option line: "0) MessageType - FILL ONLY: [...]"
            match = re.match(
                r'^(\d+)\)\s+(\w+.*?)\s*-\s*(?:FILL ONLY|BOUND):\s*\[(.*?)\]',
                stripped
            )
            if match:
                option_num = int(match.group(1))
                msg_type_full = match.group(2)
                params_str = match.group(3)
                
                # Extract message type (first word)
                msg_type = msg_type_full.split()[0]
                
                # Parse parameters
                missing_params = [p.strip() for p in params_str.split(',') if p.strip()]
                
                # Check for bound params
                bound_params = {}
                if "BOUND:" in stripped:
                    bound_match = re.search(r'BOUND:\s*\{([^}]+)\}', stripped)
                    if bound_match:
                        pairs = bound_match.group(1).split(',')
                        for pair in pairs:
                            if '=' in pair:
                                k, v = pair.split('=', 1)
                                bound_params[k.strip()] = v.strip()
                
                opt = Option(
                    option_number=option_num,
                    message_type=msg_type,
                    missing_params=missing_params,
                    bound_params=bound_params
                )
                options.append(opt)
            
            i += 1
        
        return i, options

    def _find_choice_result(self, search_start: int) -> Tuple[Optional[int], Dict[str, str], Optional[str]]:
        """Find what choice was actually made and what message was sent."""
        choice_num = None
        choice_params = {}
        message_sent = None
        
        # Look forward for "PARSED LLM RESPONSE" section
        for i in range(search_start, min(search_start + 100, len(self.lines))):
            line = self.lines[i]
            
            if "PARSED LLM RESPONSE" in line:
                # Next few lines should have the parsed choice
                for j in range(i + 1, min(i + 20, len(self.lines))):
                    parsed_line = self.lines[j]
                    if '"choice":' in parsed_line:
                        match = re.search(r'"choice":\s*(\d+|null)', parsed_line)
                        if match and match.group(1) != 'null':
                            choice_num = int(match.group(1))
                    if '"params":' in parsed_line:
                        # Try to extract params from JSON
                        try:
                            match = re.search(r'"params":\s*({[^}]+})', parsed_line)
                            if match:
                                params_json = "{" + match.group(1) + "}"
                                choice_params = json.loads(params_json)
                        except:
                            pass
                    if "Sending message:" in parsed_line:
                        # Extract message type
                        match = re.search(r'Sending message:\s*(\w+)\(', parsed_line)
                        if match:
                            message_sent = match.group(1)
                        break
        
        return choice_num, choice_params, message_sent

    def _extract_parameters_from_events(self) -> None:
        """Extract and group parameters from decision events."""
        param_map: Dict[str, Dict[str, set]] = {}
        
        for event in self.demo_data.decision_events:
            # Extract from message history
            for msg in event.message_history:
                # Try to infer protocol
                protocol = self._infer_protocol_from_roles(
                    msg.sender if hasattr(msg, 'sender') else 'Unknown'
                )
                msg.protocol = protocol
                
                for param_name, param_value in msg.parameters.items():
                    if protocol not in param_map:
                        param_map[protocol] = {}
                    if param_name not in param_map[protocol]:
                        param_map[protocol][param_name] = set()
                    param_map[protocol][param_name].add(param_value)
        
        # Convert to ParameterBinding objects
        for protocol, params in param_map.items():
            for param_name, values in params.items():
                key = f"{protocol}:{param_name}"
                self.demo_data.parameters[key] = ParameterBinding(
                    name=param_name,
                    protocol=protocol,
                    values=sorted(list(values))
                )

    def _infer_protocol_from_roles(self, role: str) -> str:
        """Infer protocol from role name."""
        if role in ['Buyer', 'Seller', 'Shipper']:
            return 'Purchase'
        elif role in ['Merchant', 'Wrapper', 'Labeler', 'Packer']:
            return 'Logistics'
        elif role in ['CreditSeller', 'CreditBuyer']:
            return 'CreditPurchase'
        else:
            return 'Unknown'

    def _extract_metrics(self) -> None:
        """Extract metrics from decision events."""
        self.demo_data.metrics.total_decision_events = len(self.demo_data.decision_events)
        
        # Collect unique protocols and roles
        protocols = set()
        roles = set()
        
        for event in self.demo_data.decision_events:
            for msg in event.message_history:
                if msg.protocol:
                    protocols.add(msg.protocol)
                roles.add((msg.protocol if msg.protocol else 'Unknown', msg.sender))
                roles.add((msg.protocol if msg.protocol else 'Unknown', msg.receiver))
        
        self.demo_data.metrics.protocols = sorted(list(protocols))
        self.demo_data.metrics.protocol_count = len(protocols)
        self.demo_data.metrics.roles = sorted(list(roles))
        
        # Count violations and exceptions
        for line in self.lines:
            line_lower = line.lower()
            if 'violation' in line_lower or ('constraint' in line_lower and 'error' in line_lower):
                self.demo_data.metrics.violations += 1
            if 'exception' in line_lower or 'traceback' in line_lower:
                self.demo_data.metrics.exceptions += 1
        
        # Extract elapsed time
        for line in self.lines:
            match = re.search(r'(\d+)s elapsed', line)
            if match:
                self.demo_data.metrics.elapsed_time_seconds = int(match.group(1))
                break

    def _extract_completion_rules(self) -> None:
        """Extract completion rules for each role."""
        for line in self.lines:
            if 'completion rule' in line.lower():
                match = re.search(
                    r'for\s+(\w+)/(\w+):\s+(.+)',
                    line
                )
                if match:
                    protocol = match.group(1)
                    role = match.group(2)
                    rule = match.group(3).strip()
                    key = f"{protocol}:{role}"
                    self.demo_data.metrics.completion_rules[key] = rule

    def to_json(self, output_path: str) -> None:
        """Write extracted data to JSON file."""
        output = {
            "metadata": {
                "source_log": str(self.log_path),
                "extraction_time": self.demo_data.extraction_timestamp,
                "status": self.demo_data.status
            },
            "decision_events": [
                {
                    "decision_number": event.decision_number,
                    "event_type": event.event_type,
                    "message_history": [
                        {
                            "number": msg.number,
                            "type": msg.message_type,
                            "sender": msg.sender,
                            "receiver": msg.receiver,
                            "parameters": msg.parameters,
                            "protocol": msg.protocol
                        }
                        for msg in event.message_history
                    ],
                    "available_options": [
                        {
                            "option_number": opt.option_number,
                            "message_type": opt.message_type,
                            "missing_params": opt.missing_params,
                            "bound_params": opt.bound_params
                        }
                        for opt in event.available_options
                    ],
                    "llm_reasoning": event.llm_reasoning,
                    "llm_choice": event.llm_choice,
                    "llm_choice_params": event.llm_choice_params,
                    "message_sent": event.message_sent
                }
                for event in self.demo_data.decision_events
            ],
            "metrics": {
                "total_decision_events": self.demo_data.metrics.total_decision_events,
                "protocols": self.demo_data.metrics.protocols,
                "protocol_count": self.demo_data.metrics.protocol_count,
                "roles": list(self.demo_data.metrics.roles),
                "violations": self.demo_data.metrics.violations,
                "exceptions": self.demo_data.metrics.exceptions,
                "elapsed_time_seconds": self.demo_data.metrics.elapsed_time_seconds,
                "completion_rules": self.demo_data.metrics.completion_rules
            },
            "parameter_isolation": {
                key: {
                    "parameter": pb.name,
                    "protocol": pb.protocol,
                    "values": pb.values,
                    "value_count": len(pb.values)
                }
                for key, pb in self.demo_data.parameters.items()
            }
        }

        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"✓ Extracted data written to: {output_path}")

    def summary(self) -> str:
        """Print extraction summary."""
        m = self.demo_data.metrics
        return f"""
=== EXTRACTION SUMMARY ===
Total Decision Events: {m.total_decision_events}
Protocols: {', '.join(m.protocols)} ({m.protocol_count})
Roles: {len(m.roles)}
Violations: {m.violations}
Exceptions: {m.exceptions}
Elapsed Time: {m.elapsed_time_seconds}s
Completion Rules: {len(m.completion_rules)}
Parameters Tracked: {len(self.demo_data.parameters)}
"""


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_demo_data.py <log_file> [output_json]")
        print("Example: python extract_demo_data.py ../../../logs/generic_agent_debug_20260210_000206.log demo3_data.json")
        sys.exit(1)

    log_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "extracted_demo_data.json"

    print(f"Extracting decision events from: {log_file}")
    extractor = ProtocolLogExtractor(log_file)
    extractor.extract_all()
    print(extractor.summary())

    extractor.to_json(output_file)
    print(f"\n✓ Ready to use extracted data for paper sections!")


if __name__ == "__main__":
    main()
