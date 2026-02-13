#!/usr/bin/env python3
"""
Test script for event injector with termination condition integration.

Verifies that when events are posted with protocol information,
termination conditions are created automatically.
"""

import sys
from pathlib import Path
import json
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.event_injector import post_event_to_agent
from lib.termination_condition_manager import (
    get_termination_condition_file,
    reset_termination_conditions,
    get_termination_condition_summary,
)


def test_event_injector_integration():
    """Test event injection with termination condition creation."""
    
    print("\n" + "="*70)
    print("EVENT INJECTOR INTEGRATION TEST")
    print("="*70)
    
    # Reset for clean state
    print("\n1. Resetting previous state...")
    reset_termination_conditions()
    
    # Clear event queue
    queue_file = Path(tempfile.gettempdir()) / "maf_events_queue.json"
    if queue_file.exists():
        queue_file.unlink()
    print("   ✓ State cleared")
    
    # Test 1: Post event WITH protocol info (should create termination condition)
    print("\n2. Posting event with protocol information...")
    success = post_event_to_agent(
        event_type="user_defined",
        message="Purchase request: Buy a bat",
        priority="high",
        metadata={
            "item": "bat",
            "delivery_address": "123 Main St",
            "budget": 29.99
        },
        protocol_name="Purchase",
        role="Buyer"
    )
    
    if success:
        print("   ✓ Event posted successfully")
    else:
        print("   ✗ Failed to post event")
        return False
    
    # Test 2: Verify termination condition was created
    print("\n3. Verifying termination condition was created...")
    condition_file = get_termination_condition_file()
    
    if condition_file.exists():
        with open(condition_file, 'r') as f:
            conditions_data = json.load(f)
        
        if conditions_data["conditions"]:
            condition = conditions_data["conditions"][0]
            print(f"   ✓ Termination condition created")
            print(f"   ✓ Event: {condition['event_description']}")
            print(f"   ✓ Protocol: {condition['protocol']}")
            print(f"   ✓ Required messages:")
            for msg in condition["required_messages"]:
                print(f"     - {msg['role']}: {msg['message_type']} ({msg['required_count']}x)")
        else:
            print("   ✗ No conditions in file")
            return False
    else:
        print("   ✗ Condition file not created")
        return False
    
    # Test 3: Post event WITHOUT protocol info (should NOT create condition)
    print("\n4. Posting event WITHOUT protocol information...")
    success = post_event_to_agent(
        event_type="user_defined",
        message="Simple event without protocol",
        priority="normal",
        metadata={"data": "test"}
    )
    
    if success:
        print("   ✓ Event posted successfully")
    else:
        print("   ✗ Failed to post event")
        return False
    
    # Verify only one condition exists
    print("\n5. Verifying no extra condition was created...")
    with open(condition_file, 'r') as f:
        conditions_data = json.load(f)
    
    if len(conditions_data["conditions"]) == 1:
        print("   ✓ Only 1 condition exists (as expected)")
    else:
        print(f"   ✗ Expected 1 condition, found {len(conditions_data['conditions'])}")
        return False
    
    # Test 4: Check event queue
    print("\n6. Verifying event queue contains both events...")
    if queue_file.exists():
        with open(queue_file, 'r') as f:
            queue_data = json.load(f)
        
        if len(queue_data["events"]) == 2:
            print(f"   ✓ Queue contains 2 events")
            for i, event in enumerate(queue_data["events"]):
                print(f"     Event {i+1}: {event['message']}")
        else:
            print(f"   ✗ Expected 2 events, found {len(queue_data['events'])}")
            return False
    else:
        print("   ✗ Event queue file not found")
        return False
    
    print("\n" + "="*70)
    print("✓ ALL INTEGRATION TESTS PASSED")
    print("="*70)
    
    return True


if __name__ == "__main__":
    success = test_event_injector_integration()
    sys.exit(0 if success else 1)
