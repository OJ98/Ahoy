#!/usr/bin/env python3
"""
Minimal test script to validate FlexiblePurchase protocol correctness.
Tests that all expected roles, messages, and protocol structure exist.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import bspl

def test_flexible_purchase_protocol():
    """Test FlexiblePurchase protocol structure."""
    
    # Load the protocol
    protocol_path = PROJECT_ROOT / "protocols" / "flexible_purchase.bspl"
    spec = bspl.load_file(str(protocol_path))
    protocol = spec.protocols.get("FlexiblePurchase")
    
    print("✓ Protocol loaded successfully")
    assert protocol is not None, "FlexiblePurchase protocol not found"
    
    # Test roles
    roles = protocol.roles
    assert "FlexibleCustomer" in roles, "FlexibleCustomer role not found"
    assert "FlexibleMerchant" in roles, "FlexibleMerchant role not found"
    print(f"✓ Roles found: {list(roles.keys())}")
    
    # Test parameters
    params = protocol.parameters
    assert "ID" in params, "ID parameter not found"
    assert "item" in params, "item parameter not found"
    assert "price" in params, "price parameter not found"
    assert "done" in params, "done parameter not found"
    print(f"✓ Parameters found: {list(params.keys())}")
    
    # Test messages - get message names using a different approach
    # Messages might be a dict or list depending on bspl version
    messages = protocol.messages
    if isinstance(messages, dict):
        message_names = set(messages.keys())
    else:
        # Try accessing as iterable
        try:
            message_names = {msg if isinstance(msg, str) else msg.name for msg in messages}
        except:
            message_names = set()
    
    expected_messages = {
        "rfq",
        "offer",
        "accept",
        "standard_delivery_request",
        "standard_delivery",
        "express_delivery_request",
        "express_delivery",
        "pay",
        "receipt"
    }
    
    # Filter out any None values
    message_names = {m for m in message_names if m}
    
    for msg in expected_messages:
        assert msg in message_names, f"Message '{msg}' not found in protocol (found: {message_names})"
    
    print(f"✓ Messages found: {sorted(message_names)}")
    
    # Test that the protocol can be exported (for agent use)
    try:
        spec.export("FlexiblePurchase")
        from FlexiblePurchase import FlexibleCustomer, FlexibleMerchant
        print(f"✓ Protocol successfully exported and imported")
    except Exception as e:
        print(f"✗ Failed to export/import protocol: {e}")
        raise
    
    print("\n✅ All protocol tests passed!")
    return True


if __name__ == "__main__":
    try:
        test_flexible_purchase_protocol()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
