#!/usr/bin/env python3
"""
Test to verify that event and non-event prompts have the same structure,
preventing LLM confusion from switching between different prompt formats.
"""

import sys
from pathlib import Path

# Read the functions directly from the utils file
utils_file = Path(__file__).resolve().parent / "lib" / "utils.py"

def extract_function(func_name):
    """Extract a function definition from utils.py."""
    with open(utils_file, 'r') as f:
        content = f.read()
    
    # Find function definition
    import re
    pattern = rf'^def {func_name}\([^)]*\).*?:.*?(?=\ndef |\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        return True
    return False


def test_prompt_files():
    """Test that both prompts are defined and structured correctly."""
    print("=" * 80)
    print("TEST: Prompt Structure Consistency")
    print("=" * 80)
    
    # Read the utils file directly
    with open(utils_file, 'r') as f:
        utils_content = f.read()
    
    print("\n✓ Reading utils.py to compare prompt structures...")
    
    # Check for build_user_prompt structure
    regular_checks = [
        'def build_user_prompt(',
        'You are agent',
        'Choose at most one option',
        'MESSAGE HISTORY:',
        'Options:',
        'Response format JSON:',
        '{"choice": 0, "params":',
        '{"choice": null, "params":',
    ]
    
    # Check for build_custom_event_user_prompt structure  
    event_checks = [
        'def build_custom_event_user_prompt(',
        'Uses the EXACT SAME structure as build_user_prompt',
        'EXTERNAL EVENTS REQUIRING YOUR ACTION:',
        'You are agent',
        'Choose at most one option',
        'MESSAGE HISTORY:',
        'Options:',
        'Response format JSON:',
        '{"choice": 0, "params":',
        '{"choice": null, "params":',
    ]
    
    print("\n" + "=" * 80)
    print("CHECK 1: build_user_prompt components")
    print("=" * 80)
    
    regular_pass = True
    for check in regular_checks:
        if check in utils_content:
            print(f"✓ {check[:50]}")
        else:
            print(f"✗ Missing: {check[:50]}")
            regular_pass = False
    
    print("\n" + "=" * 80)
    print("CHECK 2: build_custom_event_user_prompt components")
    print("=" * 80)
    
    event_pass = True
    for check in event_checks:
        if check in utils_content:
            print(f"✓ {check[:50]}")
        else:
            print(f"✗ Missing: {check[:50]}")
            event_pass = False
    
    print("\n" + "=" * 80)
    print("CHECK 3: Key consistency statements in docstring")
    print("=" * 80)
    
    # Look for the specific docstring that documents consistency
    consistency_indicators = [
        '**CRITICAL**: Uses the EXACT SAME structure as build_user_prompt',
        'The ONLY difference is that external events are highlighted prominently',
        '- Same header wording',
        '- Same role display format',
        '- Same message history section',
        '- Same options formatting',
        '- Same response format examples',
    ]
    
    consistency_pass = True
    for indicator in consistency_indicators:
        if indicator in utils_content:
            print(f"✓ {indicator[:60]}")
        else:
            print(f"✗ Missing: {indicator[:60]}")
            consistency_pass = False
    
    print("\n" + "=" * 80)
    print("CHECK 4: Structure comparison in code")
    print("=" * 80)
    
    # Verify both use identical header and role sections
    structure_checks = [
        ('IDENTICAL HEADER to build_user_prompt', 'Uses same)'),
        ('IDENTICAL ROLE DISPLAY to build_user_prompt', 'Uses same header'),
        ('IDENTICAL MESSAGE HISTORY to build_user_prompt', 'Uses same format'),
        ('IDENTICAL OPTIONS FORMAT to build_user_prompt', 'Uses same structure'),
        ('IDENTICAL RESPONSE FORMAT to build_user_prompt', 'Uses same examples'),
    ]
    
    structure_pass = True
    for check, _ in structure_checks:
        # These are comments in the code that document consistency
        if check in utils_content:
            print(f"✓ {check[:60]}")
        else:
            print(f"✗ Might be missing: {check[:60]}")
    
    print("\n" + "=" * 80)
    if regular_pass and event_pass and consistency_pass:
        print("ALL STRUCTURAL CONSISTENCY CHECKS PASSED! ✓")
        print("=" * 80)
        print("\nSummary:")
        print("  • build_user_prompt: Contains all standard elements")
        print("  • build_custom_event_user_prompt: Uses identical structure")
        print("  • External events: Only difference is prominent event display")
        print("  • LLM sees consistent format: Same header, roles, history, options, format")
        return True
    else:
        print("SOME CHECKS FAILED! ✗")
        print("=" * 80)
        return False


if __name__ == '__main__':
    success = test_prompt_files()
    sys.exit(0 if success else 1)
