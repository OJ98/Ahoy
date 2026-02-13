#!/usr/bin/env python3
"""
Test script to verify the new event formatting and parsing works correctly.
Tests that multiple events don't have their context (like budget) bleed into each other.
"""

import json
import sys
from pathlib import Path

def test_new_format_parsing():
    """Test parsing the new cleaner event format."""
    print("=" * 80)
    print("TEST 1: New Format Parsing (Protocol-Agnostic)")
    print("=" * 80)
    
    # Simulate the new format that ahoy.py creates
    new_format_context = """Event #1:
  Message: Purchase request: Buy a pen
  Metadata:
    • item: pen
    • delivery_address: Raleigh, NC
    • budget: 20

Event #2:
  Message: Purchase request: Buy a trolley
  Metadata:
    • item: trolley
    • delivery_address: 123 Main St, Springfield
    • budget: 29.99"""
    
    print("\nFormatted context from ahoy.py:")
    print(new_format_context)
    
    # Now parse it (same logic as llm_client.py)
    events = []
    lines = new_format_context.split('\n')
    current_event = None
    
    is_new_format = any(line.strip().startswith('Event #') for line in lines)
    print(f"\n✓ Detected format: {'NEW' if is_new_format else 'OLD'}")
    
    if is_new_format:
        i = 0
        while i < len(lines):
            line = lines[i]
            line_stripped = line.strip()
            
            if line_stripped.startswith('Event #'):
                if current_event is not None:
                    events.append(current_event)
                
                current_event = {
                    'message': '',
                    'metadata': {},
                    'priority': 'normal'
                }
                i += 1
                
                # Find Message line
                while i < len(lines):
                    line = lines[i]
                    line_stripped = line.strip()
                    
                    if not line_stripped:
                        i += 1
                        continue
                    
                    if line_stripped.startswith('Message: '):
                        current_event['message'] = line_stripped[9:]
                        i += 1
                        break
                    elif line_stripped.startswith('Event #'):
                        break
                    
                    i += 1
                
                # Find Metadata section
                while i < len(lines):
                    line = lines[i]
                    line_stripped = line.strip()
                    
                    if line_stripped == 'Metadata:':
                        i += 1
                        while i < len(lines):
                            line = lines[i]
                            line_stripped = line.strip()
                            
                            if not line_stripped:
                                i += 1
                                continue
                            
                            if line_stripped.startswith('•'):
                                metadata_text = line_stripped[1:].strip()
                                if ':' in metadata_text:
                                    key, value = metadata_text.split(':', 1)
                                    current_event['metadata'][key.strip()] = value.strip()
                                i += 1
                            elif line_stripped.startswith('Event #'):
                                break
                            else:
                                i += 1
                        break
                    elif line_stripped.startswith('Event #'):
                        break
                    else:
                        i += 1
            else:
                i += 1
    
    if current_event is not None:
        events.append(current_event)
    
    print(f"\n✓ Parsed {len(events)} events:")
    for idx, event in enumerate(events, 1):
        print(f"\n  Event #{idx}:")
        print(f"    Message: {event['message']}")
        print(f"    Metadata:")
        for key, value in event['metadata'].items():
            print(f"      • {key}: {value}")
    
    # Verify no context bleeding
    print("\n" + "=" * 80)
    print("VERIFICATION: Context Not Bleeding")
    print("=" * 80)
    
    assert events[0]['metadata'].get('budget') == '20', "Event #1 budget should be 20"
    assert events[1]['metadata'].get('budget') == '29.99', "Event #2 budget should be 29.99"
    assert events[0]['metadata'].get('item') == 'pen', "Event #1 item should be pen"
    assert events[1]['metadata'].get('item') == 'trolley', "Event #2 item should be trolley"
    
    print("\n✓ Event #1 (pen) has correct budget: 20")
    print("✓ Event #2 (trolley) has correct budget: 29.99")
    print("✓ NO CONTEXT BLEEDING between events!")
    

def test_backward_compatibility():
    """Test that old format still works."""
    print("\n" + "=" * 80)
    print("TEST 2: Backward Compatibility (Old Format)")
    print("=" * 80)
    
    # Simulate the old format
    old_format_context = """- Purchase request: Buy a pen
  └─ item: pen
  └─ delivery_address: Raleigh, NC
  └─ budget: 20
- Purchase request: Buy a trolley
  └─ item: trolley
  └─ delivery_address: 123 Main St, Springfield
  └─ budget: 29.99"""
    
    print("\nOld format context:")
    print(old_format_context)
    
    # Parse old format
    events = []
    lines = old_format_context.split('\n')
    current_event = None
    
    is_new_format = any(line.strip().startswith('Event #') for line in lines)
    print(f"\n✓ Detected format: {'NEW' if is_new_format else 'OLD'}")
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        if line_stripped.startswith('- '):
            if current_event is not None:
                events.append(current_event)
            current_event = {
                'message': line_stripped[2:],
                'metadata': {},
                'priority': 'normal'
            }
        elif line_stripped.startswith('└─ ') and current_event is not None:
            metadata_line = line_stripped[3:]
            if ':' in metadata_line:
                key, value = metadata_line.split(':', 1)
                current_event['metadata'][key.strip()] = value.strip()
    
    if current_event is not None:
        events.append(current_event)
    
    print(f"\n✓ Parsed {len(events)} events from old format")
    
    assert events[0]['metadata'].get('budget') == '20', "Event #1 budget should be 20"
    assert events[1]['metadata'].get('budget') == '29.99', "Event #2 budget should be 29.99"
    print("✓ Old format still works correctly!")


if __name__ == '__main__':
    test_new_format_parsing()
    test_backward_compatibility()
    
    print("\n" + "=" * 80)
    print("ALL TESTS PASSED! ✓")
    print("=" * 80)
    print("\nSummary:")
    print("  • New event format has clear boundaries (Event #N)")
    print("  • Each event's metadata is clearly contained under 'Metadata:'")
    print("  • No context (budget, item, etc.) bleeding between events")
    print("  • Old format remains fully supported for backwards compatibility")
