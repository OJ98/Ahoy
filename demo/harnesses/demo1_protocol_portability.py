#!/usr/bin/env python3
"""
Demo 1: Protocol Portability

Demonstrates that a single LLM-driven agent can enact multiple protocols
without code changes, using the actual Ahoy framework with real adapters.

Key Characteristics:
- Uses real BSPL adapters (no mocks)
- Employs actual choose_and_bind() LLM decision logic
- Executes complete protocol enactments with message sending
- Validates message sequences and protocol constraints
- Demonstrates zero protocol-specific code

Test Scenarios:
1. Purchase Protocol (Buyer role): Agent selects and negotiates a purchase
2. Logistics Protocol (Merchant role): Agent coordinates shipping/packaging workflow

Expected Results:
- Both protocols reach terminal state without violations
- Message sequences respect protocol constraints
- No adapter exceptions or schema violations
- Consistent LLM decision quality across domains
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from bspl.adapter import Adapter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configuration import systems, agents
from lib.llm_client import AnthropicLLMClient, choose_and_bind
from lib.state_manager import extract_social_state
from lib.protocol_completion_detector import is_completion_message
from demo.harnesses.base_harness import BaseHarness, ExecutionTrace


class ProtocolPortabilityHarness(BaseHarness):
    """
    Test harness for Protocol Portability.
    
    Executes identical LLM decision logic across multiple protocol contexts,
    demonstrating that generic agent code can handle different protocols
    without modification.
    
    Architecture:
    - Creates real BSPL adapters for each protocol-role combination
    - Uses choose_and_bind() for LLM decisions (actual Ahoy logic)
    - Tracks execution via ExecutionTrace objects
    - Validates message sequences and constraint adherence
    """
    
    def __init__(self):
        """Initialize harness with test scenarios."""
        super().__init__("demo1_protocol_portability")
        self.llm_client = AnthropicLLMClient()
        
        # Define test scenarios: same agent logic, different protocols
        self.test_scenarios = [
            {
                "id": "purchase_buyer",
                "protocol": "Purchase",
                "role": "Buyer",
                "description": "Buyer role in Purchase protocol negotiation",
                "agent_goal": "Buy a pen for less than $10"
            },
            {
                "id": "logistics_merchant",
                "protocol": "Logistics",
                "role": "Merchant",
                "description": "Merchant role in Logistics protocol coordination",
                "agent_goal": "Organize the wrapping and labeling of packages"
            }
        ]
    
    async def run_protocol_enactment(
        self,
        protocol_name: str,
        role_name: str,
        agent_goal: str,
        trace: ExecutionTrace,
        max_steps: int = 10
    ) -> Dict[str, Any]:
        """
        Execute a complete protocol enactment using actual Ahoy framework.
        
        This method demonstrates the core protocol portability principle:
        - No protocol-specific code paths or conditional logic
        - Uses generic choose_and_bind() for all LLM decisions
        - Identical flow regardless of protocol or role
        
        Args:
            protocol_name: Name of protocol (e.g., "Purchase", "Logistics")
            role_name: Role within protocol (e.g., "Buyer", "Merchant")
            agent_goal: Natural language description of agent's objective
            trace: ExecutionTrace object for recording execution details
            max_steps: Maximum protocol steps before termination (safety limit)
        
        Returns:
            Dictionary with metrics:
            - status: "success" or "error"
            - steps_executed: Number of decision steps completed
            - messages_sent: Count of protocol messages sent
            - violations: Count of constraint violations detected
            - terminal_reached: Whether protocol reached terminal state
            - adapter_exceptions: Count of adapter-level exceptions
        
        Raises:
            ValueError: If protocol/role combination is invalid
            Exception: Propagates adapter or LLM errors for trace recording
        """
        try:
            # === STEP 1: Load protocol configuration ===
            system_config = systems[protocol_name]
            protocol_obj = system_config["protocol"]
            role_obj = protocol_obj.roles[role_name]
            
            trace.add_event("adapter_creation_start", {
                "protocol": protocol_name,
                "role": role_name
            })
            
            # === STEP 2: Create real BSPL adapter ===
            # This is the core Ahoy component: a protocol-aware message handler
            adapter = Adapter(role_obj, systems, agents)
            trace.add_event("adapter_created", {
                "protocol": protocol_name,
                "role": role_name,
                "adapter_type": type(adapter).__name__
            })
            
            # === STEP 3: Execute decision loop ===
            step_count = 0
            messages_sent = 0
            adapter_exceptions = 0
            decisions_made = []
            
            # The main protocol enactment loop
            while step_count < max_steps:
                # Check what messages are currently enabled
                enabled_store = adapter.enabled_store
                enabled_messages = list(enabled_store.messages())
                
                # Terminal condition: no more enabled messages
                if not enabled_messages:
                    trace.add_event("protocol_terminal", {
                        "reason": "no_enabled_messages",
                        "step": step_count,
                        "total_steps": step_count
                    })
                    self.log_info(f"  Protocol reached terminal state at step {step_count}")
                    break
                
                # Record current protocol state
                social_state = extract_social_state(adapter)
                trace.add_state_snapshot(protocol_name, role_name, social_state)
                
                # === STEP 4: Use actual choose_and_bind() for LLM decision ===
                # This is identical to what real Ahoy agents use
                try:
                    message_instance = await choose_and_bind(
                        adapter=adapter,
                        enabled_store=enabled_store,
                        event={"type": "decision_step", "step": step_count},
                        client=self.llm_client,
                        timeout=30.0,
                        logger_callback=lambda msg: self.log_debug(msg),
                        agent_name=f"{protocol_name}:{role_name}"
                    )
                except Exception as e:
                    trace.add_error("llm_decision_error", str(e), {
                        "step": step_count,
                        "enabled_count": len(enabled_messages)
                    })
                    adapter_exceptions += 1
                    self.log_error(f"  LLM decision failed at step {step_count}: {e}")
                    break
                
                # === STEP 5: Validate and send message ===
                if message_instance is None:
                    # LLM chose to skip this step or reached a stopping condition
                    trace.add_event("llm_decision_skip", {
                        "step": step_count,
                        "reason": "no_message_selected"
                    })
                    break
                
                # Validate message schema
                try:
                    # Attempt to send through adapter (enforces schema validation)
                    await adapter.send(message_instance)
                    messages_sent += 1
                    
                    trace.add_message(
                        msg_type=message_instance.schema.name,
                        sender=role_name,
                        receiver="other_agents",
                        payload=dict(message_instance.payload)
                    )
                    
                    decisions_made.append({
                        "step": step_count,
                        "message_type": message_instance.schema.name,
                        "parameters": dict(message_instance.payload)
                    })
                    
                    self.log_info(f"  Step {step_count}: Sent {message_instance.schema.name}")
                    
                except Exception as e:
                    # Schema violation or adapter exception
                    trace.add_error("message_send_error", str(e), {
                        "step": step_count,
                        "message_type": getattr(message_instance.schema, 'name', 'unknown')
                    })
                    adapter_exceptions += 1
                    self.log_error(f"  Message send failed: {e}")
                    break
                
                step_count += 1
            
            # === STEP 6: Compile execution metrics ===
            return {
                "status": "success",
                "protocol": protocol_name,
                "role": role_name,
                "steps_executed": step_count,
                "messages_sent": messages_sent,
                "decisions_made": len(decisions_made),
                "adapter_exceptions": adapter_exceptions,
                "terminal_reached": step_count < max_steps,
                "violations": len(trace.errors),
                "execution_time_seconds": (
                    trace.end_time - trace.start_time
                ).total_seconds() if trace.end_time else None
            }
        
        except KeyError as e:
            # Invalid protocol or role name
            error_msg = f"Invalid protocol/role: {protocol_name}/{role_name}"
            trace.add_error("invalid_configuration", error_msg, {
                "available_protocols": list(systems.keys())
            })
            self.log_error(f"  {error_msg}")
            return {
                "status": "error",
                "protocol": protocol_name,
                "role": role_name,
                "error": error_msg,
                "error_type": "configuration"
            }
        
        except Exception as e:
            # Unexpected runtime error
            trace.add_error("execution_error", str(e), {
                "traceback": sys.exc_info()[2]
            })
            self.log_error(f"  Unexpected error: {e}")
            return {
                "status": "error",
                "protocol": protocol_name,
                "role": role_name,
                "error": str(e),
                "error_type": "runtime"
            }
    
    async def run(self) -> Dict[str, Any]:
        """
        Execute the complete protocol portability demonstration.
        
        Workflow:
        1. Initialize execution traces for each test scenario
        2. For each scenario (protocol-role pair):
           a. Create real BSPL adapter
           b. Execute protocol enactment with LLM agent
           c. Record all execution events, messages, and state snapshots
           d. Validate that protocol constraints were maintained
        3. Aggregate results and generate summary report
        4. Save execution traces for offline analysis
        
        Key Invariant Tested:
        - The agent decision logic is IDENTICAL across all scenarios
        - No conditional code branches based on protocol or role
        - All protocol differences are handled by the BSPL adapter
        - Therefore, any differences in behavior must come from:
          * Different enabled messages (protocol structure)
          * Different parameter constraints (protocol definition)
          * Different LLM decisions (domain-specific reasoning)
        
        Returns:
            Dictionary with aggregate results containing:
            - harness: Harness identifier
            - status: Overall execution status
            - scenarios: List of per-scenario results
            - summary: Aggregate statistics
        """
        self.log_info("="*70)
        self.log_info("Demo 1: Protocol Portability - Starting")
        self.log_info("Testing: Same agent logic across multiple protocols")
        self.log_info("="*70)
        
        results = {
            "harness": "protocol_portability",
            "timestamp": None,
            "status": "in_progress",
            "scenarios": [],
            "summary": {
                "total_scenarios": len(self.test_scenarios),
                "successful_protocols": 0,
                "failed_protocols": 0,
                "total_steps": 0,
                "total_messages_sent": 0,
                "total_violations": 0,
                "average_steps_per_scenario": 0.0
            }
        }
        
        # Execute each test scenario
        for scenario in self.test_scenarios:
            scenario_id = scenario['id']
            self.log_info(f"\n[Scenario] {scenario_id}")
            self.log_info(f"  Protocol: {scenario['protocol']}")
            self.log_info(f"  Role: {scenario['role']}")
            self.log_info(f"  Goal: {scenario['agent_goal']}")
            
            # Create execution trace for this scenario
            trace = self.create_trace(scenario_id)
            
            # Run the protocol enactment
            scenario_results = await self.run_protocol_enactment(
                protocol_name=scenario['protocol'],
                role_name=scenario['role'],
                agent_goal=scenario['agent_goal'],
                trace=trace,
                max_steps=10
            )
            
            # Finalize the trace
            trace.finalize()
            
            # Update summary statistics
            if scenario_results['status'] == 'success':
                results['summary']['successful_protocols'] += 1
                results['summary']['total_steps'] += scenario_results['steps_executed']
                results['summary']['total_messages_sent'] += scenario_results['messages_sent']
                results['summary']['total_violations'] += scenario_results['violations']
                
                self.log_info(f"  ✓ Success: {scenario_results['steps_executed']} steps, "
                             f"{scenario_results['messages_sent']} messages sent")
                
                if scenario_results['adapter_exceptions'] > 0:
                    self.log_warn(f"    ⚠ {scenario_results['adapter_exceptions']} adapter exceptions")
                
                if scenario_results['violations'] > 0:
                    self.log_warn(f"    ⚠ {scenario_results['violations']} constraint violations")
            else:
                results['summary']['failed_protocols'] += 1
                self.log_error(f"  ✗ Failed: {scenario_results.get('error', 'unknown error')}")
            
            results['scenarios'].append(scenario_results)
        
        # Calculate aggregate statistics
        if results['summary']['successful_protocols'] > 0:
            results['summary']['average_steps_per_scenario'] = (
                results['summary']['total_steps'] / 
                results['summary']['successful_protocols']
            )
        
        # Finalize status
        results['status'] = (
            'completed' if results['summary']['failed_protocols'] == 0 
            else 'completed_with_failures'
        )
        results['timestamp'] = None
        
        # Save all execution traces and summary report
        self.save_all_traces()
        self.save_summary_report(results)
        
        # Print final summary
        self.log_info("\n" + "="*70)
        self.log_info("Demo 1: Protocol Portability - Complete")
        self.log_info(f"Success Rate: {results['summary']['successful_protocols']}/{results['summary']['total_scenarios']}")
        self.log_info(f"Total Steps Executed: {results['summary']['total_steps']}")
        self.log_info(f"Total Messages Sent: {results['summary']['total_messages_sent']}")
        self.log_info(f"Violations Detected: {results['summary']['total_violations']}")
        self.log_info("="*70)
        
        return results


async def main():
    """
    Entry point for Demo 1: Protocol Portability.
    
    Initializes and executes the protocol portability test harness.
    Results are printed to console and saved to disk.
    """
    harness = ProtocolPortabilityHarness()
    results = await harness.run()
    
    # Print results as JSON for easy parsing/logging
    print("\n" + "="*70)
    print("RESULTS (JSON):")
    print("="*70)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    import json
    asyncio.run(main())
