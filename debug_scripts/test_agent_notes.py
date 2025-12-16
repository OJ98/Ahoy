#!/usr/bin/env python3
"""
Quick test of the new agent_notes system.
Verifies that:
1. Notes are stored as key-value pairs
2. File is named agent_notes.json
3. Notes can be saved and retrieved
4. Notes reset on each run
"""

import json
from pathlib import Path
from lib.agent_notes import get_agent_notes, reset_agent_notes

# Setup
notes_dir = Path("logs/agent_notes")
notes_file = notes_dir / "agent_notes.json"

# Test 1: Reset notes at startup
print("Test 1: Reset agent notes at startup...")
reset_agent_notes('Buyer')
reset_agent_notes('Adapter')
if notes_file.exists():
    notes_file.unlink()
print("✓ Notes reset successfully\n")

# Test 2: Save key-value pairs
print("Test 2: Save key-value pairs...")
buyer_notes = get_agent_notes('Buyer')
buyer_notes.save('procurement_constraints', 'Budget: $20.00 | Delivery: Raleigh, NC 27606')
buyer_notes.save('transaction_strategy', 'Accept first viable quote meeting all constraints')

adapter_notes = get_agent_notes('Adapter')
adapter_notes.save('vendor_selection_priority', '1) Price <= $20, 2) Delivery to 27606, 3) Pen quality')
print("✓ Key-value pairs saved successfully\n")

# Test 3: Verify file structure
print("Test 3: Verify agent_notes.json structure...")
if notes_file.exists():
    with open(notes_file, 'r') as f:
        data = json.load(f)
    
    print("File contents:")
    print(json.dumps(data, indent=2))
    
    # Check that it has the expected structure
    assert 'Buyer' in data, "Buyer data missing"
    assert 'Adapter' in data, "Adapter data missing"
    assert data['Buyer']['procurement_constraints'] == 'Budget: $20.00 | Delivery: Raleigh, NC 27606'
    assert data['Adapter']['vendor_selection_priority'] == '1) Price <= $20, 2) Delivery to 27606, 3) Pen quality'
    print("✓ File structure is correct\n")
else:
    print("✗ File was not created!\n")

# Test 4: Retrieve values
print("Test 4: Retrieve saved values...")
assert buyer_notes.get('procurement_constraints') == 'Budget: $20.00 | Delivery: Raleigh, NC 27606'
assert adapter_notes.get('vendor_selection_priority') == '1) Price <= $20, 2) Delivery to 27606, 3) Pen quality'
print("✓ Values retrieved successfully\n")

# Test 5: Get all notes
print("Test 5: Get all notes for agent...")
all_buyer_notes = buyer_notes.get_all()
print(f"Buyer notes: {all_buyer_notes}")
assert len(all_buyer_notes) == 2, "Should have 2 saved values"
print("✓ get_all() works correctly\n")

print("="*60)
print("All tests passed! ✓")
print("="*60)
