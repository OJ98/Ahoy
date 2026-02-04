#!/usr/bin/env python3
"""
Dynamic Adapter Manager - Create adapters for any protocol/role combination.
Factory for instantiating BSPL adapters dynamically.

Supports both:
- Single-role creation: create_adapter_for_role(protocol_name, role_name)
- Multi-role creation: create_adapter_for_agent(agent_identity)
"""

from typing import Optional, Tuple
from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
from lib.protocol_discovery import get_protocol_object, get_role_object
import bspl.adapter.receiver as _recv


def create_adapter_for_agent(agent_identity: str, color_index: int = 0) -> Tuple[Optional[Adapter], Optional[str]]:
    """
    Create an adapter for an agent across all their assigned roles.
    
    This is the primary method for multi-role support. The agent_identity is used to:
    1. Look up addresses from the agents configuration
    2. Determine which roles the agent plays across all systems
    3. Create a single Adapter instance that handles all those roles
    
    Args:
        agent_identity: Agent identity (string key from agents dict) 
        color_index: Color index for UI display
    
    Returns:
        tuple: (adapter, error_message) - adapter is None if error occurs
    """
    # Validate agent exists in agents configuration
    if agent_identity not in agents:
        return None, f"Agent '{agent_identity}' not found in agents configuration"
    
    if not agents[agent_identity]:
        return None, f"Agent '{agent_identity}' has no addresses configured"
    
    # Create adapter
    try:
        # Use COLORS array if index is valid, otherwise use first color
        color = COLORS[color_index] if color_index < len(COLORS) else COLORS[0]
        
        # Create adapter with agent identity (string)
        # The Adapter will look up in systems to find which roles this agent plays
        adapter = Adapter(agent_identity, systems, agents, color=color)
        
        # Register receiver
        _recv.adapter = adapter
        
        return adapter, None
    
    except Exception as e:
        return None, f"Error creating adapter for agent '{agent_identity}': {str(e)}"


def create_adapter_for_role(protocol_name: str, role_name: str, color_index: int = 0) -> Tuple[Optional[Adapter], Optional[str]]:
    """
    Create an adapter for a specific protocol and role (legacy method).
    
    DEPRECATED: For multi-role support, use create_adapter_for_agent() instead.
    This method is maintained for backward compatibility with existing agents
    that still use role-based initialization.
    
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
    
    # Look up which agent plays this role in this protocol
    agent_identity = None
    protocol_config = systems.get(protocol_name)
    if protocol_config:
        for role_obj, agent_id in protocol_config["roles"].items():
            if role_obj == role:
                agent_identity = agent_id
                break
    
    if not agent_identity:
        return None, f"No agent assigned to {protocol_name}:{role_name}"
    
    # Use agent-based creation
    return create_adapter_for_agent(agent_identity, color_index)


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

