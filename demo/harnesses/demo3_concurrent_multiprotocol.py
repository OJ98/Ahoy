#!/usr/bin/env python3
"""
Demo 3: Concurrent Multiprotocol Participation
Demonstrates simultaneous participation in multiple protocols.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from bspl.adapter import Adapter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configuration import systems, agents
from lib.llm_client import AnthropicLLMClient
from lib.state_manager import extract_social_state
from demo.harnesses.base_harness import BaseHarness, ExecutionTrace


class EventScheduler:
    """Schedules events across multiple concurrent protocols."""
    
    def __init__(self, protocol_configs: Dict[str, Dict[str, Any]]):
        self.protocol_configs = protocol_configs
        self.protocols = list(protocol_configs.keys())
        self.current_idx = 0
    
    def next_protocol(self) -> str:
        """Get next protocol in round-robin fashion."""
        protocol = self.protocols[self.current_idx % len(self.protocols)]
        self.current_idx += 1
        return protocol


class ConcurrentMultiprotocolHarness(BaseHarness):
    """
    Test harness for Concurrent Multiprotocol Participation.
    Executes agent in multiple protocols simultaneously with interleaved decisions.
    """
    
    def __init__(self):
        super().__init__("demo3_concurrent_multiprotocol")
        self.llm_client = AnthropicLLMClient()
        self.message_metrics = {"total_sent": 0, "total_skipped": 0, "send_errors": 0}
    
    async def run_concurrent_enactment(
        self,
        max_steps_per_protocol: int = 8
    ) -> Dict[str, Any]:
        """
        Execute concurrent protocol enactments with interleaved decisions.
        """
        
        # Protocol configurations
        protocol_configs = {
            "purchase": {
                "protocol": "Purchase",
                "role": "Buyer",
                "goal": "Buy a pen for less than $10",
                "adapter": None,
                "step": 0,
                "terminal": False,
                "decisions": [],
                "state_snapshots": [],
                "messages_sent": 0
            },
            "logistics": {
                "protocol": "Logistics",
                "role": "Merchant",
                "goal": "Organize wrapping and labeling of packages",
                "adapter": None,
                "step": 0,
                "terminal": False,
                "decisions": [],
                "state_snapshots": [],
                "messages_sent": 0
            }
        }
        
        trace = self.create_trace("concurrent_multiprotocol")
        
        try:
            # Initialize adapters
            for protocol_key, config in protocol_configs.items():
                protocol_name = config["protocol"]
                role_name = config["role"]
                
                system_config = systems[protocol_name]
                protocol_obj = system_config["protocol"]
                role_obj = protocol_obj.roles[role_name]
                
                adapter = Adapter(role_obj, systems, agents)
                protocol_configs[protocol_key]["adapter"] = adapter
                
                trace.add_event("adapter_initialized", {
                    "protocol_key": protocol_key,
                    "protocol": protocol_name,
                    "role": role_name
                })
                
                self.log_info(f"✓ Initialized {protocol_name}:{role_name}")
            
            # Create event scheduler
            scheduler = EventScheduler(protocol_configs)
            
            # Interleave decision steps across protocols
            total_steps = 0
            isolation_violations = []
            
            while total_steps < (max_steps_per_protocol * 2):
                protocol_key = scheduler.next_protocol()
                config = protocol_configs[protocol_key]
                
                if config["terminal"]:
                    continue
                
                if config["step"] >= max_steps_per_protocol:
                    config["terminal"] = True
                    trace.add_event("protocol_terminal", {
                        "protocol_key": protocol_key,
                        "reason": "max_steps_reached",
                        "step": config["step"]
                    })
                    continue
                
                # Get current state
                adapter = config["adapter"]
                enabled_messages = list(adapter.enabled_messages.messages())
                
                if not enabled_messages:
                    config["terminal"] = True
                    trace.add_event("protocol_terminal", {
                        "protocol_key": protocol_key,
                        "reason": "no_enabled_messages",
                        "step": config["step"]
                    })
                    continue
                
                # Record state snapshot
                adapter_state = extract_social_state(adapter)
                config["state_snapshots"].append({
                    "step": config["step"],
                    "state": adapter_state
                })
                
                trace.add_state_snapshot(
                    config["protocol"],
                    config["role"],
                    adapter_state
                )
                
                # Check for cross-protocol parameter contamination
                for other_key, other_config in protocol_configs.items():
                    if other_key != protocol_key:
                        other_adapter = other_config["adapter"]
                        other_state = extract_social_state(other_adapter)
                        
                        # Check parameter isolation
                        current_params = set(adapter_state.get('bound_parameters', {}).keys())
                        other_params = set(other_state.get('bound_parameters', {}).keys())
                        
                        # Verify parameter values are isolated across protocols
                        common_param_names = current_params & other_params
                        if common_param_names:
                            for param_name in common_param_names:
                                current_val = adapter_state.get('bound_parameters', {}).get(param_name)
                                other_val = other_state.get('bound_parameters', {}).get(param_name)
                                
                                # Same value in different protocols = contamination
                                if current_val == other_val and current_val is not None:
                                    isolation_violations.append({
                                        "protocol1": protocol_key,
                                        "protocol2": other_key,
                                        "parameter": param_name,
                                        "shared_value": current_val,
                                        "step": config["step"]
                                    })
                                    trace.add_error("parameter_contamination", 
                                        f"Parameter {param_name} shares value across protocols at step {config['step']}")
                
                # Make LLM decision
                enabled_formatted = []
                for msg in enabled_messages:
                    enabled_formatted.append({
                        "message_type": msg.schema.name,
                        "ins": list(msg.schema.ins),
                        "outs": list(msg.schema.outs)
                    })
                
                self.log_debug(f"  {protocol_key} step {config['step']}: {len(enabled_messages)} enabled messages")
                
                decision = await self._get_llm_decision(
                    protocol_key,
                    config,
                    enabled_formatted,
                    adapter_state
                )
                
                if decision:
                    config["decisions"].append({
                        "step": config["step"],
                        "decision": decision
                    })
                    trace.add_event("llm_decision", {
                        "protocol_key": protocol_key,
                        "step": config["step"],
                        "decision_type": decision.get("type", "unknown")
                    })
                    
                    # Execute message decision
                    message_sent = await self._execute_message_decision(
                        protocol_key,
                        config,
                        decision,
                        enabled_messages,
                        adapter,
                        trace
                    )
                    
                    if message_sent:
                        self.log_debug(f"    ✓ Message sent via {protocol_key}")
                        self.message_metrics["total_sent"] += 1
                        config["messages_sent"] += 1
                    else:
                        self.log_debug(f"    - Skipped message for {protocol_key}")
                        self.message_metrics["total_skipped"] += 1
                else:
                    self.message_metrics["total_skipped"] += 1
                
                config["step"] += 1
                total_steps += 1
            
            # Finalize trace with metrics
            trace.metrics = {
                "total_steps": total_steps,
                "isolation_violations": len(isolation_violations),
                "messages_sent": self.message_metrics["total_sent"],
                "messages_skipped": self.message_metrics["total_skipped"],
                "send_errors": self.message_metrics["send_errors"]
            }
            trace.finalize()
            
            # Collect results
            results = {
                "status": "success",
                "protocols_executed": len(protocol_configs),
                "total_interleaved_steps": total_steps,
                "isolation_violations": len(isolation_violations),
                "protocol_results": {}
            }
            
            for protocol_key, config in protocol_configs.items():
                results["protocol_results"][protocol_key] = {
                    "protocol": config["protocol"],
                    "role": config["role"],
                    "steps": config["step"],
                    "decisions": len(config["decisions"]),
                    "messages_sent": config["messages_sent"],
                    "terminal": config["terminal"],
                    "state_snapshots": len(config["state_snapshots"])
                }
                
                self.log_info(f"  {protocol_key}: {config['step']} steps, {len(config['decisions'])} decisions, {config['messages_sent']} messages sent")
            
            # Check isolation
            results["isolation_check"] = {
                "violations": isolation_violations,
                "passed": len(isolation_violations) == 0
            }
            
            # Log summary
            self.log_info(f"\nMessage Summary: {self.message_metrics['total_sent']} sent, {self.message_metrics['total_skipped']} skipped")
            if isolation_violations:
                self.log_error(f"Parameter isolation violations detected: {len(isolation_violations)}")
            else:
                self.log_info("✓ Parameter isolation maintained across protocols")
            
            return results
        
        except Exception as e:
            trace.add_error("execution_error", str(e))
            trace.finalize()
            self.log_error(f"Error in concurrent execution: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _get_llm_decision(
        self,
        protocol_key: str,
        config: Dict[str, Any],
        enabled_messages: list,
        adapter_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Query LLM for decision with protocol context."""
        try:
            message_types = [m['message_type'] for m in enabled_messages]
            prompt = f"""You are playing {config['role']} in {config['protocol']} protocol.

Your goal: {config['goal']}

Current state:
- Step: {config['step']}
- Bound parameters: {adapter_state.get('bound_parameters', {})}
- Message history: {len(adapter_state.get('message_history', []))} messages

Enabled messages you can send:
{', '.join(message_types)}

Choose one message type to send, or respond SKIP.
Response format: {{"message": "MessageName"}}
"""
            
            self.log_debug(f"  Querying LLM for {protocol_key}: {message_types}")
            
            response = await self.llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                model="claude-haiku-4-5-20251001"
            )
            
            self.log_debug(f"  LLM response: {response[:100] if len(response) > 100 else response}")
            
            return {
                "type": "message_selection",
                "response": response
            }
        
        except Exception as e:
            self.log_error(f"LLM decision error in {protocol_key}: {e}")
            return None
    
    async def _execute_message_decision(
        self,
        protocol_key: str,
        config: Dict[str, Any],
        decision: Dict[str, Any],
        enabled_messages: list,
        adapter: Adapter,
        trace: ExecutionTrace
    ) -> bool:
        """Parse LLM decision and execute message send. Returns True if message was sent."""
        try:
            response = decision.get("response", "").lower()
            
            # Check if LLM chose to skip
            if "skip" in response:
                return False
            
            # Find matching message from enabled messages
            for msg in enabled_messages:
                msg_name = msg.schema.name.lower()
                if msg_name in response or response.find(msg_name) >= 0:
                    # Send the message
                    await adapter.send(msg)
                    trace.add_message(
                        msg.schema.name,
                        config["role"],
                        "participant",
                        {"step": config["step"], "protocol": config["protocol"]}
                    )
                    return True
            
            # If no exact match found, try to send the first message as fallback
            if enabled_messages and "skip" not in response:
                await adapter.send(enabled_messages[0])
                trace.add_message(
                    enabled_messages[0].schema.name,
                    config["role"],
                    "participant",
                    {"step": config["step"], "protocol": config["protocol"], "note": "fallback_selection"}
                )
                return True
            
            return False
        
        except Exception as e:
            trace.add_error("message_execution_error", str(e))
            self.log_error(f"Failed to execute message decision in {protocol_key}: {e}")
            self.message_metrics["send_errors"] += 1
            return False
    
    async def run(self) -> Dict[str, Any]:
        """Execute concurrent multiprotocol demonstration."""
        self.log_info("="*70)
        self.log_info("Starting Demo 3: Concurrent Multiprotocol Participation")
        self.log_info("="*70)
        
        results = {
            "harness": "concurrent_multiprotocol",
            "status": "completed",
            "enactment_results": await self.run_concurrent_enactment(),
            "summary": {}
        }
        
        # Build summary
        if results["enactment_results"]["status"] == "success":
            enum_results = results["enactment_results"]
            results["summary"] = {
                "protocols_active": enum_results["protocols_executed"],
                "total_steps": enum_results["total_interleaved_steps"],
                "parameter_isolation": enum_results["isolation_check"]["passed"],
                "isolation_violations": enum_results["isolation_check"]["violations"]
            }
        
        self.save_all_traces()
        self.save_summary_report(results)
        
        self.log_info("\n" + "="*70)
        if results["enactment_results"]["status"] == "success":
            self.log_info(f"Demo 3 Complete - {results['enactment_results']['protocols_executed']} protocols, "
                         f"{results['enactment_results']['total_interleaved_steps']} steps")
        else:
            self.log_error(f"Demo 3 Failed - {results['enactment_results']['error']}")
        self.log_info("="*70)
        
        return results


async def main():
    """Run the concurrent multiprotocol harness."""
    harness = ConcurrentMultiprotocolHarness()
    results = await harness.run()
    print("\n" + "="*70)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
