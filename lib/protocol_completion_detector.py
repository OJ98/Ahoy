#!/usr/bin/env python3
"""
Protocol Completion Detector - Identify final messages per role.
Auto-detects when a role has completed its protocol participation.
"""

from typing import Dict, Optional
from lib.protocol_discovery import get_protocol_structure


# Manual mapping of final messages per role
# Format: {protocol_name: {role_name: final_message_name}}
COMPLETION_RULES = {
    "Purchase": {
        "Buyer": "completed",
        "Seller": "completed",
        "Shipper": "deliver",
    },
    "Logistics": {
        "Merchant": "Packed",
        "Wrapper": "Wrapped",
        "Labeler": "Labeled",
        "Packer": "Packed",
    }
}


def get_completion_message(protocol_name: str, role_name: str) -> Optional[str]:
    """
    Get the completion message name for a given protocol/role.
    
    Args:
        protocol_name: Name of protocol
        role_name: Name of role
    
    Returns:
        str: Message name that indicates completion, or None
    """
    if protocol_name in COMPLETION_RULES:
        return COMPLETION_RULES[protocol_name].get(role_name)
    return None


def is_completion_message(protocol_name: str, role_name: str, message_name: str) -> bool:
    """
    Check if a message indicates role completion.
    
    Args:
        protocol_name: Name of protocol
        role_name: Name of role
        message_name: Name of message being sent
    
    Returns:
        bool: True if this message completes the role
    """
    completion_msg = get_completion_message(protocol_name, role_name)
    if completion_msg is None:
        return False
    
    return message_name.lower() == completion_msg.lower()


def get_all_completion_rules() -> Dict[str, Dict[str, str]]:
    """
    Get all completion rules.
    
    Returns:
        dict: Full completion rules mapping
    """
    return COMPLETION_RULES.copy()
