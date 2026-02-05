#!/usr/bin/env python3
"""
Dynamic Adapter Manager - Create adapters for any protocol/role combination.
Factory for instantiating BSPL adapters dynamically.

Supports both:
- Single-role creation: create_adapter_for_role(protocol_name, role_name)
- Multi-role creation: create_adapter_for_agent(agent_identity)
"""

from typing import Optional, Tuple, List, Dict
from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
from lib.protocol_discovery import get_protocol_object, get_role_object
import bspl.adapter.receiver as _recv

# Cache for agent role resolutions  
_agent_roles_cache: Dict[str, List[Tuple[str, object]]] = {}


def get_agent_role_objects(agent_identity: str) -> List[Tuple[str, object]]:
    """
    Resolve an agent identity string to a list of (protocol_name, role_object) tuples.
    
    This is needed because the BSPL Adapter expects Role objects, not agent strings.
    For multi-role agents, this identifies all the roles the agent is assigned to.
    
    Args:
        agent_identity: Agent identity string (e.g., "ahoy", "Buyer")
    
    Returns:
        List of (protocol_name, role_object) tuples
    """
    # Check cache first
    if agent_identity in _agent_roles_cache:
        return _agent_roles_cache[agent_identity]
    
    role_objects = []
    
    # Search through all systems for roles assigned to this agent
    for system_name, system_config in systems.items():
        role_map = system_config.get("roles", {})
        for role_obj, assigned_agent in role_map.items():
            if assigned_agent == agent_identity:
                role_objects.append((system_name, role_obj))
    
    # Cache the result
    _agent_roles_cache[agent_identity] = role_objects
    return role_objects


def create_adapter_for_agent(agent_identity: str, color_index: int = 0) -> Tuple[Optional[Adapter], Optional[str]]:
    """
    Create an adapter for an agent across all their assigned roles.
    
    The BSPL Adapter class automatically discovers and manages ALL roles
    that an agent plays across all protocols. It expects the agent name
    string and the systems dict. From these, it determines:
    1. All Role objects the agent is assigned to
    2. Sets up message handling for all those roles simultaneously
    
    Args:
        agent_identity: Agent identity string (e.g., "ahoy", "Buyer")
        color_index: Color index for UI display
    
    Returns:
        tuple: (adapter, error_message) - adapter is None if error occurs
    """
    # Validate agent exists in agents configuration
    if agent_identity not in agents:
        return None, f"Agent '{agent_identity}' not found in agents configuration"
    
    if not agents[agent_identity]:
        return None, f"Agent '{agent_identity}' has no addresses configured"
    
    # Verify agent is assigned to at least one role
    role_objects = get_agent_role_objects(agent_identity)
    if not role_objects:
        return None, f"Agent '{agent_identity}' is not assigned to any roles in systems"
    
    try:
        # Use COLORS array if index is valid, otherwise use first color
        color = COLORS[color_index] if color_index < len(COLORS) else COLORS[0]
        
        # Create adapter with agent name string (not Role object!)
        # The Adapter will automatically discover all roles for this agent from systems dict
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


def get_all_roles_for_agent(agent_identity: str) -> List[Tuple[str, str]]:
    """
    Get all (protocol_name, role_name) string pairs for an agent.
    
    This returns role names as strings (not objects), which is useful for
    agent code that tracks roles by name (like ahoy.py).
    
    Args:
        agent_identity: Agent identity string
    
    Returns:
        List of (protocol_name, role_name) tuples
    """
    result = []
    role_objects = get_agent_role_objects(agent_identity)
    
    for protocol_name, role_obj in role_objects:
        # Get the role name from the role object
        role_name = role_obj.name if hasattr(role_obj, 'name') else str(role_obj)
        result.append((protocol_name, role_name))
    
    return result


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

