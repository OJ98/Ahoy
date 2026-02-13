#!/usr/bin/env python3
"""
Test script for termination condition manager.

Demonstrates:
1. Creating termination conditions from events
2. Updating progress as messages are processed
3. Retrieving condition summary
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.termination_condition_manager import (
    create_or_update_termination_condition,
    update_termination_condition_progress,
    get_termination_condition_summary,
    get_termination_condition_file,
    reset_termination_conditions,
)
import json


def test_termination_conditions():
    """Test the termination condition manager."""
    
    print("\n" + "="*70)
    print("TERMINATION CONDITION MANAGER TEST")
    print("="*70)
    
    # Reset for fresh start
    print("\n1. Resetting termination conditions...")
    reset_termination_conditions()
    print("   ✓ Termination conditions cleared")
    
    # Define completion rules for testing
    completion_rules = {
        ("Purchase", "Buyer"): ("completed", "send", 1),
        ("Purchase", "Seller"): ("completed", "send", 1),
        ("Logistics", "Merchant"): ("Packed", "receive", 1),
    }
    
    # Test 1: Create termination condition from event
    print("\n2. Creating termination condition from event...")
    event_msg = "Purchase request: Buy a pen"
    event_meta = {
        "item": "pen",
        "delivery_address": "Raleigh, NC 27606",
        "budget": 29.99,
        "quantity": 1
    }
    
    created = create_or_update_termination_condition(
        event_message=event_msg,
        event_metadata=event_meta,
        protocol_name="Purchase",
        completion_rules=completion_rules,
        agent_identity="buyer_agent"
    )
    
    if created:
        print("   ✓ Termination condition created successfully")
    else:
        print("   ✗ Failed to create termination condition")
        return False
    
    # Test 2: Retrieve condition file
    print("\n3. Verifying termination condition file...")
    condition_file = get_termination_condition_file()
    if condition_file.exists():
        with open(condition_file, 'r') as f:
            data = json.load(f)
        print(f"   ✓ Condition file exists: {condition_file}")
        print(f"   ✓ Contains {len(data['conditions'])} condition(s)")
        
        if data['conditions']:
            condition = data['conditions'][0]
            print(f"   ✓ Event: {condition['event_description']}")
            print(f"   ✓ Protocol: {condition['protocol']}")
            print(f"   ✓ Item Count: {condition['item_count']}")
            print(f"   ✓ Termination Criteria:")
            for criteria in condition['termination_criteria']:
                print(f"     - {criteria}")
    else:
        print("   ✗ Condition file not found")
        return False
    
    # Test 3: Get condition summary
    print("\n4. Retrieving condition summary...")
    try:
        summary = get_termination_condition_summary()
        print(f"   ✓ Total conditions: {summary['total_conditions']}")
        print(f"   ✓ Pending: {summary['pending']}")
        print(f"   ✓ Completed: {summary['completed']}")
        
        if summary['conditions']:
            for cond in summary['conditions']:
                print(f"\n   Condition: {cond['id']}")
                print(f"     Event: {cond['event']}")
                print(f"     Protocol: {cond['protocol']}")
                for prog in cond['progress']:
                    print(f"     Progress - {prog['role']}: {prog['message']} {prog['progress']}")
    except Exception as e:
        print(f"   ✗ Error retrieving summary: {e}")
        return False
    
    # Test 4: Update progress
    print("\n5. Updating termination condition progress...")
    condition_id = data['conditions'][0]['id']
    
    # Simulate receiving completed messages
    try:
        updated = update_termination_condition_progress(
            condition_id=condition_id,
            role="Buyer",
            message_type="completed",
            new_count=1
        )
        
        if updated:
            print(f"   ✓ Updated Buyer completion progress")
            
            # Check summary again
            summary_after = get_termination_condition_summary()
            print(f"   ✓ Pending conditions after update: {summary_after['pending']}")
            print(f"   ✓ Completed conditions after update: {summary_after['completed']}")
            
            if summary_after['conditions']:
                for cond in summary_after['conditions']:
                    for prog in cond['progress']:
                        if prog['role'] == 'Buyer':
                            print(f"     Buyer progress: {prog['progress']}")
        else:
            print(f"   ✗ Failed to update progress")
            return False
    except Exception as e:
        print(f"   ✗ Error updating progress: {e}")
        return False
    
    # Test 5: Create multiple conditions
    print("\n6. Testing multiple concurrent conditions...")
    event_msg_2 = "Purchase request: Buy a pen and a notebook"
    event_meta_2 = {
        "items": ["pen", "notebook"],
        "delivery_address": "123 Main St",
        "budget": 50.00
    }
    
    created_2 = create_or_update_termination_condition(
        event_message=event_msg_2,
        event_metadata=event_meta_2,
        protocol_name="Purchase",
        completion_rules=completion_rules,
        agent_identity="buyer_agent"
    )
    
    if created_2:
        print("   ✓ Second condition created")
        
        # Get final summary
        final_summary = get_termination_condition_summary()
        print(f"   ✓ Total conditions: {final_summary['total_conditions']}")
        print(f"   ✓ Pending: {final_summary['pending']}")
    else:
        print("   ✗ Failed to create second condition")
        return False
    
    print("\n" + "="*70)
    print("✓ ALL TESTS PASSED")
    print("="*70)
    print(f"\nCondition file location: {condition_file}")
    print(f"View with: cat {condition_file}")
    
    return True


if __name__ == "__main__":
    success = test_termination_conditions()
    sys.exit(0 if success else 1)
