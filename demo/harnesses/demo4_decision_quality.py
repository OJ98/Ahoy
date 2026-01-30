#!/usr/bin/env python3
"""
Demo 4: Decision Quality Across Domains
Evaluates semantic appropriateness of LLM decisions in different protocols.
"""

import asyncio
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from bspl.adapter import Adapter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configuration import systems, agents
from lib.llm_client import AnthropicLLMClient
from lib.state_manager import extract_social_state
from demo.harnesses.base_harness import BaseHarness, ExecutionTrace


class DecisionQualityEvaluator:
    """Evaluates semantic appropriateness of decisions."""
    
    def __init__(self, llm_client: AnthropicLLMClient):
        self.llm_client = llm_client
    
    async def evaluate_decision_semantics(
        self,
        scenario: str,
        decision: str,
        domain_context: str
    ) -> Dict[str, Any]:
        """
        Use LLM to evaluate semantic appropriateness of a decision.
        
        Returns: {score (1-5), reasoning, appropriate (bool)}
        """
        
        evaluation_prompt = f"""You are evaluating the semantic appropriateness of an agent decision.

Domain Context:
{domain_context}

Scenario:
{scenario}

Agent Decision:
{decision}

Rate the appropriateness on a scale of 1-5:
1 = Clearly inappropriate (violates domain logic)
2 = Questionable (might not make sense)
3 = Neutral (could work, but not optimal)
4 = Good (reasonable choice)
5 = Excellent (clear optimal choice)

Respond with JSON: {{"score": <1-5>, "reasoning": "...", "appropriate": <true/false>}}
"""
        
        try:
            response = await self.llm_client.complete(
                messages=[{"role": "user", "content": evaluation_prompt}],
                model="claude-haiku-4-5-20251001"
            )
            
            # Parse JSON response
            import json
            result = json.loads(response)
            return result
        
        except Exception as e:
            return {
                "score": 0,
                "reasoning": f"Evaluation failed: {str(e)}",
                "appropriate": False
            }


class DecisionQualityHarness(BaseHarness):
    """
    Test harness for Decision Quality Across Domains.
    Evaluates LLM reasoning quality in different protocol contexts.
    """
    
    def __init__(self):
        super().__init__("demo4_decision_quality")
        self.llm_client = AnthropicLLMClient()
        self.evaluator = DecisionQualityEvaluator(self.llm_client)
        
        self.test_scenarios = [
            {
                "id": "purchase_price_negotiation",
                "protocol": "Purchase",
                "role": "Buyer",
                "decision_point": "Price negotiation",
                "domain_context": """
In the Purchase protocol, a Buyer negotiates with a Seller.
The Buyer has a budget constraint ($5-15 for a pen).
Decisions involve:
- Which price to accept
- Whether to accept offers
- When to make counter-offers
""",
                "test_case": {
                    "scenario": "Seller offers a pen for $12. Your budget is $10-15.",
                    "decision": "Accept the offer at $12",
                    "domain_logic": "Price is within budget range, decision is reasonable"
                }
            },
            {
                "id": "logistics_material_selection",
                "protocol": "Logistics",
                "role": "Wrapper",
                "decision_point": "Wrapping material selection",
                "domain_context": """
In the Logistics protocol, a Wrapper selects wrapping material.
The selection depends on item fragility:
- Fragile items (plates, glasses) → bubble wrap
- Robust items (books, tools) → paper
- Mixed items → bubble wrap for safety
The Wrapper makes intelligent material choices without explicit rules.
""",
                "test_case": {
                    "scenario": "Item to wrap: glass plate",
                    "decision": "Select bubble wrap",
                    "domain_logic": "Glass is fragile, bubble wrap is protective"
                }
            },
            {
                "id": "purchase_no_deal",
                "protocol": "Purchase",
                "role": "Buyer",
                "decision_point": "Accepting or rejecting offer",
                "domain_context": """
In the Purchase protocol, a Buyer can:
1. Accept a seller's offer (end negotiation)
2. Make a counter-offer (continue negotiation)
3. Abandon negotiation (no deal)
Budget for pen: $5-8 (tight constraint)
""",
                "test_case": {
                    "scenario": "Seller's lowest offer is $15 for a pen. Your budget is $5-8.",
                    "decision": "Reject the offer and abandon negotiation",
                    "domain_logic": "Offer is outside budget, rejection is rational"
                }
            },
            {
                "id": "logistics_shipping_priority",
                "protocol": "Logistics",
                "role": "Packer",
                "decision_point": "Packing priority",
                "domain_context": """
In the Logistics protocol, a Packer prepares orders.
Decisions involve:
- Order of packing operations
- When to mark items complete
- Handling multiple pending orders
Priority: high-value items or time-sensitive orders first
""",
                "test_case": {
                    "scenario": "Two orders pending: Order A (2 items, standard), Order B (1 item, express). Pack Order B first.",
                    "decision": "Prioritize express order",
                    "domain_logic": "Express shipping indicates urgency, should be prioritized"
                }
            }
        ]
    
    async def evaluate_scenario(
        self,
        scenario_spec: Dict[str, Any],
        trace: ExecutionTrace
    ) -> Dict[str, Any]:
        """Evaluate a single scenario."""
        
        scenario_id = scenario_spec['id']
        test_case = scenario_spec['test_case']
        
        self.log_info(f"\nEvaluating: {scenario_id}")
        self.log_info(f"  Decision point: {scenario_spec['decision_point']}")
        self.log_info(f"  Scenario: {test_case['scenario']}")
        self.log_info(f"  Decision: {test_case['decision']}")
        
        # Get LLM evaluation
        evaluation = await self.evaluator.evaluate_decision_semantics(
            scenario=test_case['scenario'],
            decision=test_case['decision'],
            domain_context=scenario_spec['domain_context']
        )
        
        trace.add_event("decision_evaluated", {
            "scenario": scenario_id,
            "evaluation_score": evaluation.get('score', 0),
            "appropriate": evaluation.get('appropriate', False)
        })
        
        result = {
            "id": scenario_id,
            "protocol": scenario_spec['protocol'],
            "role": scenario_spec['role'],
            "decision_point": scenario_spec['decision_point'],
            "scenario": test_case['scenario'],
            "decision": test_case['decision'],
            "domain_logic": test_case['domain_logic'],
            "evaluation": evaluation
        }
        
        # Log results
        score = evaluation.get('score', 0)
        appropriate = evaluation.get('appropriate', False)
        if appropriate:
            self.log_info(f"  ✓ Score: {score}/5 - {evaluation.get('reasoning', '')}")
        else:
            self.log_error(f"  ✗ Score: {score}/5 - {evaluation.get('reasoning', '')}")
        
        return result
    
    async def run(self) -> Dict[str, Any]:
        """Execute decision quality demonstration."""
        
        self.log_info("="*70)
        self.log_info("Starting Demo 4: Decision Quality Across Domains")
        self.log_info("="*70)
        
        results = {
            "harness": "decision_quality",
            "status": "completed",
            "evaluations": [],
            "summary": {
                "total_scenarios": len(self.test_scenarios),
                "highly_appropriate": 0,  # Score >= 4
                "appropriate": 0,         # Score >= 3
                "questionable": 0,        # Score 2
                "inappropriate": 0,       # Score 1
                "average_score": 0.0
            }
        }
        
        scores = []
        
        for scenario in self.test_scenarios:
            trace = self.create_trace(scenario['id'])
            
            evaluation_result = await self.evaluate_scenario(scenario, trace)
            results['evaluations'].append(evaluation_result)
            
            score = evaluation_result['evaluation'].get('score', 0)
            scores.append(score)
            
            # Update summary statistics
            if score >= 4:
                results['summary']['highly_appropriate'] += 1
            elif score >= 3:
                results['summary']['appropriate'] += 1
            elif score == 2:
                results['summary']['questionable'] += 1
            elif score == 1:
                results['summary']['inappropriate'] += 1
        
        # Calculate average
        if scores:
            results['summary']['average_score'] = sum(scores) / len(scores)
        
        # Save results
        self.save_all_traces()
        self.save_summary_report(results)
        
        self.log_info("\n" + "="*70)
        self.log_info(f"Demo 4 Complete - Average decision score: {results['summary']['average_score']:.2f}/5.0")
        self.log_info(f"  Highly appropriate: {results['summary']['highly_appropriate']}")
        self.log_info(f"  Appropriate: {results['summary']['appropriate']}")
        self.log_info(f"  Questionable: {results['summary']['questionable']}")
        self.log_info(f"  Inappropriate: {results['summary']['inappropriate']}")
        self.log_info("="*70)
        
        return results


async def main():
    """Run the decision quality harness."""
    harness = DecisionQualityHarness()
    results = await harness.run()
    print("\n" + "="*70)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
