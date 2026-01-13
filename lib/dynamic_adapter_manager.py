#!/usr/bin/env python3
"""
Dynamic Adapter Manager - Create adapters for any protocol/role combination.
Factory for instantiating BSPL adapters dynamically.
"""

from typing import Optional, Tuple
from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
from lib.protocol_discovery import get_protocol_object, get_role_object
import bspl.adapter.receiver as _recv


def create_adapter_for_role(protocol_name: str, role_name: str, color_index: int = 0) -> Tuple[Optional[Adapter], Optional[str]]:
    """
    Create an adapter for a specific protocol and role.
    
    Args:
        protocol_name: Name of the protocol (e.g., "Purchase", "Logistics")
        role_name: Name of the role (e.g., "Buyer", "Seller")
        color_index: Color index for UI display
    
    Returns:
        tuple: (adapter, error_message) - adapter is None if error occurs
    """
    # Validate protocol exists
    protocol = get_protocol_object(protocol_name)
    if not protocol:
        return None, f"Protocol '{protocol_name}' not found"
    
    # Validate role exists in protocol
    role = get_role_object(protocol_name, role_name)
    if not role:
        return None, f"Role '{role_name}' not found in protocol '{protocol_name}'"
    
    # Create adapter
    try:
        # Use COLORS array if index is valid, otherwise use first color
        color = COLORS[color_index] if color_index < len(COLORS) else COLORS[0]
        adapter = Adapter(role, systems, agents, color=color)
        
        # Register receiver
        _recv.adapter = adapter
        
        return adapter, None
    
    except Exception as e:
        return None, f"Error creating adapter: {str(e)}"


def get_color_for_protocol_role(protocol_name: str, role_name: str) -> int:
    """
    Get a consistent color index for a protocol/role combination.
    
    Args:
        protocol_name: Name of protocol
        role_name: Name of role
    
    Returns:
        int: Color index from COLORS array
    """
    # Create a hash-based color assignment for consistency
    combined = f"{protocol_name}:{role_name}"
    color_idx = hash(combined) % len(COLORS)
    return max(0, color_idx)
