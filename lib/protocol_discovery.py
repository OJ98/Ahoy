#!/usr/bin/env python3
"""
Protocol Discovery - Load and analyze all available protocols.
Extracts protocol structure for LLM decision-making.
"""

from typing import Dict, List, Any
from configuration import systems


def get_all_protocols() -> Dict[str, Any]:
    """
    Get all available protocols from configuration.
    
    Returns:
        dict: Mapping of protocol name -> protocol object
    """
    protocols = {}
    for proto_name, proto_data in systems.items():
        if proto_name and proto_data.get("protocol"):
            protocols[proto_name] = proto_data["protocol"]
    return protocols


def get_protocol_structure(protocol_name: str) -> Dict[str, Any]:
    """
    Get detailed structure of a specific protocol.
    
    Args:
        protocol_name: Name of the protocol (e.g., "Purchase", "Logistics")
    
    Returns:
        dict: Protocol structure with roles and messages
    """
    protocols = get_all_protocols()
    if protocol_name not in protocols:
        return None
    
    protocol = protocols[protocol_name]
    
    # Extract roles
    roles = list(protocol.roles.keys()) if hasattr(protocol, 'roles') else []
    
    # Extract messages
    messages = []
    if hasattr(protocol, 'messages'):
        for msg in protocol.messages:
            if hasattr(msg, 'name'):
                messages.append(msg.name)
    
    return {
        "name": protocol_name,
        "roles": [role.name if hasattr(role, 'name') else str(role) for role in roles],
        "messages": messages,
        "protocol_obj": protocol
    }


def get_protocol_summary_for_llm() -> str:
    """
    Generate human-readable protocol summary for LLM context.
    
    Returns:
        str: Formatted protocol information
    """
    protocols = get_all_protocols()
    
    if not protocols:
        return "No protocols available."
    
    summary = "Available Protocols:\n"
    for proto_name in sorted(protocols.keys()):
        structure = get_protocol_structure(proto_name)
        if structure:
            roles_str = ", ".join(structure["roles"])
            summary += f"\n- {proto_name}: roles [{roles_str}]"
    
    return summary


def validate_protocol_and_role(protocol_name: str, role_name: str) -> tuple:
    """
    Validate that protocol and role exist.
    
    Args:
        protocol_name: Name of protocol
        role_name: Name of role
    
    Returns:
        tuple: (is_valid, error_message)
    """
    structure = get_protocol_structure(protocol_name)
    
    if not structure:
        return False, f"Protocol '{protocol_name}' not found"
    
    if role_name not in structure["roles"]:
        available_roles = ", ".join(structure["roles"])
        return False, f"Role '{role_name}' not found in {protocol_name}. Available: {available_roles}"
    
    return True, None


def get_protocol_object(protocol_name: str):
    """
    Get the protocol object for a given protocol name.
    
    Args:
        protocol_name: Name of the protocol
    
    Returns:
        Protocol object or None
    """
    structure = get_protocol_structure(protocol_name)
    if structure:
        return structure["protocol_obj"]
    return None


def get_role_object(protocol_name: str, role_name: str):
    """
    Get the Role object for a given protocol and role name.
    
    Args:
        protocol_name: Name of the protocol
        role_name: Name of the role
    
    Returns:
        Role object or None
    """
    protocol = get_protocol_object(protocol_name)
    if not protocol:
        return None
    
    # Try direct dictionary access first (most efficient)
    if hasattr(protocol, 'roles') and isinstance(protocol.roles, dict):
        if role_name in protocol.roles:
            return protocol.roles[role_name]
    
    # Fallback: iterate through roles and match by name
    if hasattr(protocol, 'roles'):
        for role in protocol.roles:
            role_str = role.name if hasattr(role, 'name') else str(role)
            if role_str == role_name:
                return role
    
    return None
