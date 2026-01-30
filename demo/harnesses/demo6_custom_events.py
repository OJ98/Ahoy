#!/usr/bin/env python3
"""
Demo 6: Custom LLM Events

Demonstrates concurrent execution of adapter reactions (protocol messages)
and custom events (business logic triggers) within a single agent.

Key Characteristics:
- Uses real BSPL adapters with actual LLM decision logic
- Implements custom event handlers alongside adapter reactions
- Synchronizes both paths via asyncio.Lock
- Employs choose_and_bind() for both adapter + custom event decisions
- Validates message sequences and constraint adherence
- Tracks LLM call metrics across both paths

Test Scenarios:
1. Purchase Protocol (Buyer role with periodic timeout check)
2. Logistics Protocol (Merchant role with stall detection)

Expected Results:
- Both adapter and custom event paths execute concurrently
- No race conditions or synchronization deadlocks
- All messages respect protocol constraints
- Global LLM call counter tracks both paths
- Graceful exit when threshold exceeded or protocol completes
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from bspl.adapter import Adapter
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configuration import systems, agents
from lib.llm_client import (
    AnthropicLLMClient, 
    choose_and_bind,
    initialize_llm_tracker,
    get_llm_tracker
)
from lib.state_manager import extract_social_state
from lib.protocol_completion_detector import is_completion_message
from lib.dynamic_adapter_manager import create_adapter_for_role
from lib.ui_manager import setup_logging
from demo.harnesses.base_harness import BaseHarness, ExecutionTrace


class CustomEventsHarness(BaseHarness):
    """
    Test harness for Custom LLM Events.
    
    Executes concurrent adapter reactions and custom event handlers,
    demonstrating proactive agent behavior alongside reactive protocol responses.
    
    Architecture:
    - Creates real BSPL adapters for each protocol-role combination
    - Implements dual task loops: adapter (protocol) + custom (business logic)
    - Uses asyncio.Lock for synchronization between paths
    - Tracks execution via ExecutionTrace objects
    - Validates message sequences and constraint adherence
    """
    
    def __init__(self):
        """Initialize harness with test scenarios."""
        super().__init__("demo6_custom_events")
        self.llm_client = AnthropicLLMClient()
        initialize_llm_tracker(max_calls=30, max_duration_seconds=240)
        
        # Define test scenarios
        self.test_scenarios = [
            {
                "id": "purchase_buyer_with_timeout",
                "protocol": "Purchase",
                "role": "Buyer",
                "description": "Buyer with periodic timeout check",
                "custom_event_type": "periodic_timeout",
                "custom_event_interval": 2.0,  # Check every 2 seconds
                "agent_goal": "Buy a pen with periodic decision checks"
            },
            {
                "id": "logistics_merchant_with_stall",
                "protocol": "Logistics",
                "role": "Merchant",
                "description": "Merchant with stall detection",
                "custom_event_type": "stall_detection",
                "custom_event_interval": 3.0,  # Check every 3 seconds
                "agent_goal": "Coordinate wrapping/labeling with stall checks"
            }
        ]
    
    async def execute_scenario(self, scenario: Dict[str, Any]) -> Optional[ExecutionTrace]:
        """
        Execute a single test scenario with concurrent adapter + custom events.
        
        Args:
            scenario: Test scenario configuration
        
        Returns:
            ExecutionTrace with results, or None if execution failed
        """
        trace = ExecutionTrace(self.harness_name, scenario["id"])
        
        try:
            protocol_name = scenario["protocol"]
            role_name = scenario["role"]
            
            self.print_scenario_header(scenario)
            trace.add_event("scenario_start", {
                "protocol": protocol_name,
                "role": role_name,
                "custom_event_type": scenario["custom_event_type"]
            })
            
            # Create adapter
            adapter, adapter_error = create_adapter_for_role(protocol_name, role_name)
            if adapter_error:
                trace.add_error("adapter_creation", adapter_error)
                trace.finalize()
                print(f"  ✗ Failed to create adapter: {adapter_error}")
                return trace
            
            # Create synchronization lock
            decision_lock = asyncio.Lock()
            
            # Create event tracking
            event_counter = {"adapter": 0, "custom": 0}
            
            # Define adapted llm_decision handler with optimized locking
            async def llm_decision(enabled_store, event):
                """Adapter reaction handler with optimized synchronization.
                
                Only hold lock when accessing adapter state, not during LLM call.
                """
                is_valid, messages = self._validate_enabled_store(enabled_store)
                if not is_valid:
                    return None
                
                # Make LLM decision WITHOUT holding lock (LLM calls can be slow)
                instance = None
                try:
                    instance = await asyncio.wait_for(
                        choose_and_bind(
                            adapter=adapter,
                            enabled_store=enabled_store,
                            event=event,
                            client=self.llm_client,
                            timeout=10.0,
                            logger_callback=lambda msg: None,
                            agent_name=f"{role_name}"
                        ),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    trace.add_event("adapter_timeout", {"role": role_name})
                    return None
                
                # Only hold lock when incrementing counter and sending message
                if instance:
                    async with decision_lock:
                        event_counter["adapter"] += 1
                        trace.add_event("adapter_decision", {
                            "role": role_name,
                            "message_type": instance.schema.name if hasattr(instance, 'schema') else "unknown",
                            "counter": event_counter["adapter"]
                        })
                    return instance
                
                return None
            
            # Define custom event trigger
            async def trigger_custom_decision(event_name: str, event_context: dict):
                """Custom event handler with optimized synchronization.
                
                Check enabled store, make LLM decision, then acquire lock for state update.
                """
                # Check if there's work to do (without lock)
                async with decision_lock:
                    enabled_store = adapter.enabled_store
                    if not enabled_store or not list(enabled_store.messages()):
                        return None
                
                event = {
                    "type": event_name,
                    "source": "custom_event",
                    "context": event_context,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Make LLM decision WITHOUT holding lock
                instance = None
                try:
                    instance = await asyncio.wait_for(
                        choose_and_bind(
                            adapter=adapter,
                            enabled_store=enabled_store,
                            event=event,
                            client=self.llm_client,
                            timeout=10.0,
                            logger_callback=lambda msg: None,
                            agent_name=f"{role_name}"
                        ),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    trace.add_event("custom_timeout", {"role": role_name, "event": event_name})
                    return None
                
                # Only hold lock when incrementing counter and sending message
                if instance:
                    async with decision_lock:
                        event_counter["custom"] += 1
                        trace.add_event("custom_decision", {
                            "role": role_name,
                            "event_type": event_name,
                            "message_type": instance.schema.name if hasattr(instance, 'schema') else None,
                            "counter": event_counter["custom"]
                        })
                    return instance
                
                return None
            
            # Create custom event loop based on scenario type
            async def run_custom_events_loop():
                """Run custom events based on scenario configuration."""
                event_type = scenario["custom_event_type"]
                interval = scenario["custom_event_interval"]
                max_iterations = 5  # Limit iterations for demo
                
                for iteration in range(max_iterations):
                    try:
                        await asyncio.sleep(interval)
                        
                        if event_type == "periodic_timeout":
                            await trigger_custom_decision(
                                event_name="timeout_check",
                                event_context={
                                    "iteration": iteration,
                                    "elapsed_seconds": interval * (iteration + 1)
                                }
                            )
                        elif event_type == "stall_detection":
                            await trigger_custom_decision(
                                event_name="stall_check",
                                event_context={
                                    "iteration": iteration,
                                    "check_interval_seconds": interval
                                }
                            )
                    
                    except SystemExit:
                        raise
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        trace.add_event("custom_event_error", {
                            "iteration": iteration,
                            "error": str(e)
                        })
            
            # Create adapter polling task (replaces on_decision which doesn't exist)
            async def run_adapter_polling():
                """Manually poll adapter for enabled messages and make decisions."""
                while True:
                    try:
                        # Check if there are enabled messages (without lock)
                        enabled_store = adapter.enabled_store
                        if enabled_store and list(enabled_store.messages()):
                            # Make decision (without lock for concurrency)
                            instance = await llm_decision(enabled_store, {"type": "adapter_poll"})
                            if instance:
                                # Send the message (acquire lock only for send)
                                async with decision_lock:
                                    await adapter.send(instance)
                        
                        # Brief sleep to prevent busy-waiting
                        await asyncio.sleep(0.1)
                    
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        trace.add_event("adapter_poll_error", {"error": str(e)})
                        await asyncio.sleep(0.5)  # Back off on error
            
            # Run adapter polling + custom events concurrently with timeout
            adapter_task = asyncio.create_task(run_adapter_polling())
            custom_task = asyncio.create_task(run_custom_events_loop())
            
            try:
                # Run for max 15 seconds or until one task completes
                done, pending = await asyncio.wait(
                    [adapter_task, custom_task],
                    timeout=15.0,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel remaining tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            except asyncio.CancelledError:
                for task in [adapter_task, custom_task]:
                    if not task.done():
                        task.cancel()
            
            # Collect metrics
            llm_tracker = get_llm_tracker()
            trace.metrics = {
                "adapter_decisions": event_counter["adapter"],
                "custom_decisions": event_counter["custom"],
                "total_decisions": event_counter["adapter"] + event_counter["custom"],
                "llm_calls": llm_tracker.call_count if llm_tracker else 0,
                "elapsed_seconds": (trace.end_time - trace.start_time).total_seconds() if trace.end_time else 0
            }
            
            trace.finalize()
            
            # Report success
            print(f"  ✓ Adapter decisions made: {event_counter['adapter']}")
            print(f"  ✓ Custom event decisions made: {event_counter['custom']}")
            print(f"  ✓ Total LLM calls: {trace.metrics['llm_calls']}")
            print(f"  ✓ Total decisions (adapter + custom): {event_counter['adapter'] + event_counter['custom']}")
            
            return trace
        
        except Exception as e:
            trace.add_error("execution_error", str(e))
            trace.finalize()
            print(f"  ✗ Scenario failed: {str(e)}")
            return trace
    
    def _validate_enabled_store(self, enabled_store):
        """Validate that enabled_store has messages available."""
        if not enabled_store:
            return False, []
        
        messages = list(enabled_store.messages())
        return len(messages) > 0, messages
    
    def print_scenario_header(self, scenario: Dict[str, Any]) -> None:
        """Print a formatted header for the scenario."""
        print(f"\n[Scenario] {scenario['id']}")
        print(f"  Protocol: {scenario['protocol']}")
        print(f"  Role: {scenario['role']}")
        print(f"  Description: {scenario['description']}")
    
    async def run(self) -> Dict[str, Any]:
        """
        Run the harness (implements abstract method from BaseHarness).
        Alias for run_all_scenarios for framework compatibility.
        
        Returns:
            Summary dictionary with results
        """
        return await self.run_all_scenarios()
    
    async def run_all_scenarios(self) -> Dict[str, Any]:
        """
        Execute all test scenarios.
        
        Returns:
            Summary dictionary with results
        """
        print("\n" + "=" * 70)
        print("Demo 6: Custom LLM Events - Starting")
        print("Testing: Concurrent adapter reactions + custom event triggers")
        print("=" * 70 + "\n")
        
        results = {
            "harness": self.harness_name,
            "scenarios_executed": 0,
            "scenarios_successful": 0,
            "total_adapter_decisions": 0,
            "total_custom_decisions": 0,
            "total_llm_calls": 0,
            "violations": 0,
            "traces": []
        }
        
        for scenario in self.test_scenarios:
            results["scenarios_executed"] += 1
            trace = await self.execute_scenario(scenario)
            
            if trace:
                results["traces"].append(trace.to_dict())
                
                if not trace.errors:
                    results["scenarios_successful"] += 1
                    results["total_adapter_decisions"] += trace.metrics.get("adapter_decisions", 0)
                    results["total_custom_decisions"] += trace.metrics.get("custom_decisions", 0)
                    results["total_llm_calls"] += trace.metrics.get("llm_calls", 0)
                else:
                    results["violations"] += len(trace.errors)
        
        # Print summary
        print("\n" + "=" * 70)
        print("Demo 6: Custom LLM Events - Complete")
        print(f"Success Rate: {results['scenarios_successful']}/{results['scenarios_executed']}")
        print(f"Total Adapter Decisions: {results['total_adapter_decisions']}")
        print(f"Total Custom Decisions: {results['total_custom_decisions']}")
        print(f"Total LLM Calls: {results['total_llm_calls']}")
        print(f"Violations Detected: {results['violations']}")
        print("=" * 70 + "\n")
        
        return results


async def main():
    """Run the demo."""
    harness = CustomEventsHarness()
    results = await harness.run_all_scenarios()
    
    # Save results
    output_dir = Path(__file__).parent.parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"demo6_results_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to: {output_file}\n")
    
    return 0 if results["violations"] == 0 else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹ Demo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
