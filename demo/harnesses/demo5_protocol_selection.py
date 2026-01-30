#!/usr/bin/env python3
"""
Demo 5: Protocol Selection Accuracy
Tests the protocol selection module's ability to map user intent to protocols/roles.
"""

import asyncio
import csv
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.protocol_discovery import (
    get_all_protocols,
    get_protocol_summary_for_llm,
    validate_protocol_and_role
)
from lib.llm_client import AnthropicLLMClient
from demo.harnesses.base_harness import BaseHarness, ExecutionTrace


class ProtocolSelectionTester:
    """Tests protocol selection accuracy."""
    
    def __init__(self, llm_client: AnthropicLLMClient):
        self.llm_client = llm_client
        self.protocols = get_all_protocols()
    
    async def select_protocol_and_role(self, user_input: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Use LLM to select protocol and role from user input.
        Returns (protocol_name, role_name) or (None, None) on failure.
        """
        
        protocol_summary = get_protocol_summary_for_llm()
        
        prompt = f"""You are a protocol selection assistant. Based on the user's goal, determine which protocol and role are most appropriate.

{protocol_summary}

User's Goal:
{user_input}

Respond with ONLY the protocol and role in this exact format:
PROTOCOL: <ProtocolName>
ROLE: <RoleName>

Be concise. Do not explain."""
        
        try:
            response = await self.llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                model="claude-haiku-4-5-20251001"
            )
            
            # Parse response
            lines = response.strip().split('\n')
            protocol = None
            role = None
            
            for line in lines:
                if line.startswith("PROTOCOL:"):
                    protocol = line.split(":", 1)[1].strip()
                elif line.startswith("ROLE:"):
                    role = line.split(":", 1)[1].strip()
            
            if protocol and role:
                # Validate
                is_valid = validate_protocol_and_role(protocol, role)
                if is_valid:
                    return (protocol, role)
            
            return (None, None)
        
        except Exception as e:
            print(f"Error in protocol selection: {e}")
            return (None, None)


class ProtocolSelectionHarness(BaseHarness):
    """
    Test harness for Protocol Selection Accuracy.
    Tests how well the selection module maps user intents to protocols/roles.
    """
    
    def __init__(self):
        super().__init__("demo5_protocol_selection")
        self.llm_client = AnthropicLLMClient()
        self.tester = ProtocolSelectionTester(self.llm_client)
        
        # Test cases: (user_input, expected_protocol, expected_role, difficulty)
        self.test_cases = [
            # Clear Purchase intents
            {
                "id": "clear_purchase_1",
                "input": "I want to buy a notebook",
                "expected_protocol": "Purchase",
                "expected_role": "Buyer",
                "difficulty": "easy",
                "category": "clear_purchase"
            },
            {
                "id": "clear_purchase_2",
                "input": "I need to purchase office supplies",
                "expected_protocol": "Purchase",
                "expected_role": "Buyer",
                "difficulty": "easy",
                "category": "clear_purchase"
            },
            {
                "id": "clear_purchase_3",
                "input": "Sell me a pen for $5",
                "expected_protocol": "Purchase",
                "expected_role": "Seller",
                "difficulty": "easy",
                "category": "clear_purchase"
            },
            {
                "id": "clear_purchase_4",
                "input": "I'm a shipper and need to deliver packages",
                "expected_protocol": "Purchase",
                "expected_role": "Shipper",
                "difficulty": "easy",
                "category": "clear_purchase"
            },
            
            # Clear Logistics intents
            {
                "id": "clear_logistics_1",
                "input": "I need to wrap and label packages at my warehouse",
                "expected_protocol": "Logistics",
                "expected_role": "Merchant",
                "difficulty": "easy",
                "category": "clear_logistics"
            },
            {
                "id": "clear_logistics_2",
                "input": "I'm a wrapper and need to wrap delicate items",
                "expected_protocol": "Logistics",
                "expected_role": "Wrapper",
                "difficulty": "easy",
                "category": "clear_logistics"
            },
            {
                "id": "clear_logistics_3",
                "input": "I need to label items with unique identifiers",
                "expected_protocol": "Logistics",
                "expected_role": "Labeler",
                "difficulty": "medium",
                "category": "clear_logistics"
            },
            {
                "id": "clear_logistics_4",
                "input": "Pack the orders and prepare them for shipment",
                "expected_protocol": "Logistics",
                "expected_role": "Packer",
                "difficulty": "medium",
                "category": "clear_logistics"
            },
            
            # Ambiguous intents
            {
                "id": "ambiguous_1",
                "input": "I want to ship something",
                "expected_protocol": "Purchase",
                "expected_role": "Shipper",
                "difficulty": "hard",
                "category": "ambiguous"
            },
            {
                "id": "ambiguous_2",
                "input": "Handle my packages",
                "expected_protocol": "Logistics",
                "expected_role": "Merchant",
                "difficulty": "hard",
                "category": "ambiguous"
            },
            {
                "id": "ambiguous_3",
                "input": "Coordinate an exchange of goods",
                "expected_protocol": "Purchase",
                "expected_role": "Buyer",
                "difficulty": "hard",
                "category": "ambiguous"
            },
            
            # Complex multi-agent scenarios
            {
                "id": "complex_1",
                "input": "I'm managing a supply chain where items need to be wrapped, labeled, and packaged",
                "expected_protocol": "Logistics",
                "expected_role": "Merchant",
                "difficulty": "hard",
                "category": "complex"
            },
            {
                "id": "complex_2",
                "input": "I need to buy supplies, negotiate prices, and arrange delivery",
                "expected_protocol": "Purchase",
                "expected_role": "Buyer",
                "difficulty": "hard",
                "category": "complex"
            },
        ]
    
    async def test_single_selection(
        self,
        test_case: Dict[str, Any],
        trace: ExecutionTrace
    ) -> Dict[str, Any]:
        """Test a single protocol selection."""
        
        user_input = test_case['input']
        expected_protocol = test_case['expected_protocol']
        expected_role = test_case['expected_role']
        
        self.log_debug(f"Testing: {test_case['id']} - {user_input}")
        
        # Get LLM selection
        selected_protocol, selected_role = await self.tester.select_protocol_and_role(user_input)
        
        # Determine if correct
        correct = (selected_protocol == expected_protocol and selected_role == expected_role)
        
        trace.add_event("selection_tested", {
            "test_case_id": test_case['id'],
            "correct": correct,
            "expected": f"{expected_protocol}:{expected_role}",
            "selected": f"{selected_protocol}:{selected_role}"
        })
        
        result = {
            "test_case_id": test_case['id'],
            "input": user_input,
            "expected_protocol": expected_protocol,
            "expected_role": expected_role,
            "selected_protocol": selected_protocol,
            "selected_role": selected_role,
            "correct": correct,
            "difficulty": test_case['difficulty'],
            "category": test_case['category']
        }
        
        return result
    
    async def run(self) -> Dict[str, Any]:
        """Execute protocol selection accuracy demonstration."""
        
        self.log_info("="*70)
        self.log_info("Starting Demo 5: Protocol Selection Accuracy")
        self.log_info("="*70)
        
        results = {
            "harness": "protocol_selection",
            "status": "completed",
            "test_results": [],
            "summary": {
                "total_tests": len(self.test_cases),
                "correct": 0,
                "incorrect": 0,
                "accuracy": 0.0,
                "by_difficulty": {
                    "easy": {"correct": 0, "total": 0},
                    "medium": {"correct": 0, "total": 0},
                    "hard": {"correct": 0, "total": 0}
                },
                "by_category": {}
            }
        }
        
        # Run all tests
        for i, test_case in enumerate(self.test_cases):
            trace = self.create_trace(f"selection_test_{i}")
            
            test_result = await self.test_single_selection(test_case, trace)
            results['test_results'].append(test_result)
            
            # Update summary
            difficulty = test_case['difficulty']
            category = test_case['category']
            
            results['summary']['by_difficulty'][difficulty]['total'] += 1
            if test_result['correct']:
                results['summary']['correct'] += 1
                results['summary']['by_difficulty'][difficulty]['correct'] += 1
                self.log_info(f"✓ {test_case['id']}: CORRECT")
            else:
                results['summary']['incorrect'] += 1
                self.log_error(f"✗ {test_case['id']}: INCORRECT")
                self.log_error(f"  Expected: {test_result['expected_protocol']}:{test_result['expected_role']}")
                self.log_error(f"  Selected: {test_result['selected_protocol']}:{test_result['selected_role']}")
            
            # Track by category
            if category not in results['summary']['by_category']:
                results['summary']['by_category'][category] = {"correct": 0, "total": 0}
            results['summary']['by_category'][category]['total'] += 1
            if test_result['correct']:
                results['summary']['by_category'][category]['correct'] += 1
        
        # Calculate accuracy
        if results['summary']['total_tests'] > 0:
            results['summary']['accuracy'] = results['summary']['correct'] / results['summary']['total_tests']
        
        # Calculate per-difficulty accuracy
        for difficulty in results['summary']['by_difficulty']:
            stats = results['summary']['by_difficulty'][difficulty]
            if stats['total'] > 0:
                stats['accuracy'] = stats['correct'] / stats['total']
        
        # Calculate per-category accuracy
        for category in results['summary']['by_category']:
            stats = results['summary']['by_category'][category]
            if stats['total'] > 0:
                stats['accuracy'] = stats['correct'] / stats['total']
        
        # Save results
        self.save_all_traces()
        self.save_summary_report(results)
        
        # Save results as CSV for analysis
        csv_path = self.results_dir / "demo5_protocol_selection_results.csv"
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'test_case_id', 'input', 'expected_protocol', 'expected_role',
                'selected_protocol', 'selected_role', 'correct', 'difficulty', 'category'
            ])
            writer.writeheader()
            writer.writerows(results['test_results'])
        self.log_info(f"Saved CSV results to {csv_path}")
        
        # Print summary
        self.log_info("\n" + "="*70)
        self.log_info("Protocol Selection Accuracy Summary")
        self.log_info("="*70)
        self.log_info(f"Overall Accuracy: {results['summary']['accuracy']:.1%} ({results['summary']['correct']}/{results['summary']['total_tests']})")
        self.log_info("\nBy Difficulty:")
        for difficulty in ['easy', 'medium', 'hard']:
            stats = results['summary']['by_difficulty'][difficulty]
            if stats['total'] > 0:
                acc = stats['correct'] / stats['total']
                self.log_info(f"  {difficulty.upper()}: {acc:.1%} ({stats['correct']}/{stats['total']})")
        
        self.log_info("\nBy Category:")
        for category in sorted(results['summary']['by_category'].keys()):
            stats = results['summary']['by_category'][category]
            if stats['total'] > 0:
                acc = stats['correct'] / stats['total']
                self.log_info(f"  {category}: {acc:.1%} ({stats['correct']}/{stats['total']})")
        
        self.log_info("="*70)
        
        return results


async def main():
    """Run the protocol selection harness."""
    harness = ProtocolSelectionHarness()
    results = await harness.run()
    print("\n" + "="*70)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
