#!/usr/bin/env python3
"""
Minimal utility functions for the multi-agent system.
Provides: message history building, user prompt construction, and adapter shutdown.
"""

import asyncio
import os
import uuid
from typing import Any, Dict, Optional, Union, List, Tuple

# ============================================================================
# MODULE-LEVEL CACHES FOR OPTIMIZATION
# ============================================================================
_message_history_cache = {}  # Cache key: hash(all_messages_json)
_protocol_guidance_cache = {}  # Cache key: (protocol_name, agent_name)
_previous_message_state = None  # Track previous state to invalidate cache


# ============================================================================
# PROMPT CONTENT STRINGS
# ============================================================================

def _generate_protocol_aware_guidance(agent_names: List[str]) -> str:
    """
    Generate protocol-aware guidance based on the agent's role(s).
    
    This function extracts the protocol structure to understand what messages
    a role is responsible for sending, and guides the LLM accordingly.
    
    Args:
        agent_names: List of agent role names (e.g., ["Merchant"] or ["Merchant", "Buyer"])
    
    Returns:
        String with protocol-aware guidance for the LLM
    """
    try:
        from lib.protocol_discovery import get_all_protocols
        
        protocols = get_all_protocols()
        guidance = "\n\nPROTOCOL-SPECIFIC GUIDANCE FOR YOUR ROLE(S):\n"
        guidance += "=" * 70 + "\n"
        
        for protocol_name, protocol in protocols.items():
            for agent_name in agent_names:
                # Find this agent's role in the protocol
                if hasattr(protocol, 'roles') and agent_name in protocol.roles.keys():
                    role = protocol.roles[agent_name]
                    guidance += f"\nIn {protocol_name} protocol, your role ({agent_name}) is responsible for:\n"
                    
                    # Analyze messages this role can send
                    messages_to_send = []
                    if hasattr(protocol, 'messages'):
                        for msg in protocol.messages:
                            # Check if this role is the sender (source) of this message
                            if hasattr(msg, 'source') and hasattr(msg.source, 'name'):
                                if msg.source.name == agent_name:
                                    msg_name = msg.name if hasattr(msg, 'name') else str(msg)
                                    messages_to_send.append(msg_name)
                    
                    if messages_to_send:
                        # Remove duplicates and sort
                        messages_to_send = sorted(list(set(messages_to_send)))
                        guidance += f"  - SENDING these message types: {', '.join(messages_to_send)}\n"
                        guidance += f"    → You may need to send MULTIPLE different message types as the protocol progresses\n"
                        guidance += f"    → Some messages can be sent in parallel (not strictly sequential)\n"
                        guidance += f"    → When you see multiple message options with the same bound parameters, you can send them both (in separate decisions)\n"
                        guidance += f"    → Do not assume you only send one type of message\n"
                        guidance += f"    → Coordinate sending all required message types to advance the protocol\n"
        
        return guidance
    except Exception as e:
        # If protocol analysis fails, return empty string (graceful degradation)
        return ""


# ============================================================================
# SYSTEM PROMPT BUILDING
# ============================================================================

def build_system_prompt(agent_names: Union[str, List[str]], requirements_file: str = "input.txt") -> str:
    """
    Build a system prompt for single or multi-protocol agent scenarios.
    
    Reads user instructions and constraints from a text file to use as the system prompt.
    Supports both single agent and multiple agents (multi-protocol).
    
    Args:
        agent_names: Single agent name string, or list of agent names for multi-protocol
        requirements_file: Path to the text file with requirements/constraints (default: "input.txt")
        The file should contain the agent's instructions and constraints.
    
    Returns:
        System prompt string for the LLM (file contents + context)
    
    Raises:
        FileNotFoundError: If the requirements file cannot be found
    """
    try:
        # Normalize agent_names to list
        if isinstance(agent_names, str):
            agent_names_list = [agent_names]
            is_multi_protocol = False
        else:
            agent_names_list = agent_names if isinstance(agent_names, list) else [str(agent_names)]
            is_multi_protocol = len(agent_names_list) > 1
        
        # Try to find the file: first in current directory, then in parent directory
        import sys
        cwd = os.getcwd()
        
        if not os.path.exists(requirements_file):
            parent_file = os.path.join('..', requirements_file)
            if os.path.exists(parent_file):
                requirements_file = parent_file
        
        if not os.path.exists(requirements_file):
            # Also try looking from PROJECT_ROOT if available
            try:
                from pathlib import Path
                project_root = Path(__file__).resolve().parent.parent
                alt_file = project_root / requirements_file
                if alt_file.exists():
                    requirements_file = str(alt_file)
            except:
                pass
        
        with open(requirements_file, 'r', encoding='utf-8') as f:
            enhanced_prompt = f.read()
            if not enhanced_prompt.strip():
                raise ValueError(f"Requirements file '{requirements_file}' is empty")
            
            # Build agent introduction
            if is_multi_protocol:
                agents_str = ", ".join(agent_names_list)
                enhanced_prompt = f"You are enacting MULTIPLE roles: {agents_str}.\n\nThe user has communicated the requirements to be as follows: {enhanced_prompt}. The following is an explanation of the environment in which you operate: \n\n"
            else:
                enhanced_prompt = f"You are a {agent_names_list[0]} agent.\n\nThe user has communicated the requirements to be as follows: {enhanced_prompt}. The following is an explanation of the environment in which you operate: \n\n"

            # BSPL Protocol Explanation Strings
            bspl_highlevel_explanation = """
            You are participating in BSPL (Blindingly Simple Protocol Language) protocol enactments. 
            BSPL defines multi-agent protocols where:
            - Roles are named agents (e.g., Merchant, Buyer)
            - Messages are directed communication between roles with parameters marked as `out` (sender provides) or `in` (requires prior binding from other messages)
            - Parameters marked `key` identify protocol instances
            """
            
            if is_multi_protocol:
                bspl_highlevel_explanation += """
            - You play MULTIPLE roles across different protocols simultaneously
            - Each role has its own message flow and state
            - You must carefully coordinate which role acts at each step
            - Consider protocol dependencies and prioritize appropriately
            """
            else:
                bspl_highlevel_explanation += """
            - You play one role and must track received messages to determine which messages you can legally send next
            - A message can only be sent when all its `in` parameters are bound by prior messages
            - When multiple messages are enabled, choose based on domain reasoning and the protocol's intended flow"""
            
            enhanced_prompt = enhanced_prompt + bspl_highlevel_explanation
            
            # Add protocol-aware guidance
            protocol_guidance = _generate_protocol_aware_guidance(agent_names_list)
            if protocol_guidance:
                enhanced_prompt = enhanced_prompt + protocol_guidance
 
            # Consolidated Option Selection & Parameter Guidance
            option_selection = """
            Your choice will directly determine what message gets SENT and what happens next:
            - The BOUND parameters shown above (in [BOUND: ...]) are already set and will be used
            - You only need to provide values for parameters marked in FILL ONLY
            - Your selection will trigger protocol actions based on the message type and parameters
            
            CRITICAL: BOUND PARAMETERS ARE READY TO USE
            - When you see a message option with [BOUND: orderID=xyz, ...], those parameters are ALREADY SET
            - BOUND parameters do NOT mean the message is "blocked" or "already sent"
            - BOUND parameters mean the system has AUTO-PROVIDED those values for you to use
            - Do NOT skip or avoid options just because they have BOUND parameters
            - BOUND parameters are HELPFUL - they reduce the number of values you need to fill in
            - Example: "RequestWrapping [BOUND: orderID=123]" means you can use orderID=123 in your wrapping request
            
            IMPORTANT: When multiple message options are available, carefully consider which ones you need to send:
            - Do NOT assume you only need to send one message type
            - Some protocols require sending BOTH RequestLabel AND RequestWrapping for the same order (they are PARALLEL, not sequential)
            - Parallel messages can be sent in separate decisions - you will see them again in the next decision cycle
            - If the protocol needs both message A and message B to be sent by your role, you should send BOTH (in separate decisions)
            - Only return null if NO viable messages are available right now
            
            PREFERENCE ORDER for message selection:
            1. Options with BOUND parameters (these are ready to use immediately)
            2. Options requiring all parameters (these still need your input)
            3. null (only if absolutely no viable option exists)
            
            CRITICAL PARAMETER RULES:
            1. Parameters marked [BOUND: ...] are ALREADY SET - do NOT provide them
            2. Parameters marked 'FILL ONLY: [...]' are the ONLY ones you should provide
            3. If you choose an option, provide values for ALL FILL ONLY parameters
            4. Do not provide values for BOUND parameters - they will cause errors
            5. Either provide all required FILL ONLY params, or choose null.
            
            AVAILABLE TOOLS:
            1. **save_state_to_memory** - Records decisions for later recall
               Parameters: agent_name, key (state name), value (state content)
            
            ID MANAGEMENT:
            - The system AUTOMATICALLY generates unique IDs for ID parameters (marked as 'key')
            - You DO NOT need to generate IDs - they're created automatically
            - Simply select the option you want, and required IDs will be generated
            - Only provide IDs if explicitly required as 'FILL ONLY' parameters
            
            RESPONSE FORMAT:
            - To choose: {"choice": 0, "params": {"field": "value"}, "tool_requests": []}
            - To decline: {"choice": null, "params": {}, "tool_requests": []}
            - For tools: include tool_requests array with {"tool": "name", "args": {...}}
            
            DECISION RULE: Always choose if you have viable parameters.
            Return null only if NO viable option exists.
            """
            enhanced_prompt = enhanced_prompt + option_selection
            return enhanced_prompt
    except FileNotFoundError:
        raise FileNotFoundError(
            f"System prompt file '{requirements_file}' not found. "
            f"Please create it with your agent's instructions and constraints."
        )


# ============================================================================
# ADAPTER MANAGEMENT: Graceful shutdown
# ============================================================================

async def shutdown_watcher(adapter, stop_path: str = None):
    """Watch for stop signal file and gracefully shut down the adapter."""
    if stop_path is None:
        stop_path = str(Path(tempfile.gettempdir()) / "maf_stop_signal.txt")
    while True:
        if os.path.exists(stop_path):
            try:
                for r in getattr(adapter, "receivers", []):
                    if hasattr(r, "stop"):
                        await r.stop()
                if hasattr(adapter.emitter, "stop"):
                    await adapter.emitter.stop()
            except Exception as e:
                if hasattr(adapter, 'warning'):
                    adapter.warning(f"Error during shutdown: {e}")
            adapter.running = False
            break
        await asyncio.sleep(0.5)


# ============================================================================
# MESSAGE HISTORY: Build formatted message context for LLM
# ============================================================================

def build_message_history_from_social_state(
    social_state: Dict[str, Any],
    agent_name: Optional[str] = None,
    max_history: int = 50,
    use_cache: bool = True
) -> str:
    """Build a formatted history of past messages from social state.
    
    Constructs a human-readable summary of recent messages for LLM context,
    optionally filtered to messages sent to a specific agent/role.
    
    Uses module-level cache to avoid rebuilding identical history multiple times
    during a single decision cycle.
    
    For multirole adapters, filters messages by actual role names (e.g., "Buyer", "Merchant")
    rather than adapter name (e.g., "ahoy"), since recipients are role names.
    
    Args:
        social_state: Extracted social state dictionary
        agent_name: Optional agent name to filter by (for single-role adapters)
        max_history: Maximum number of recent messages to include
        use_cache: Whether to use caching (default: True)
    
    Returns:
        Formatted message history as a string
    """
    global _message_history_cache, _previous_message_state
    
    # Extract all messages from social state
    # Try new top-level location first (after fix), then fall back to systems entries
    all_messages = social_state.get("all_messages", [])
    if not all_messages and "systems" in social_state:
        # Fall back to old structure (systems entries)
        for system_info in social_state["systems"].values():
            if "all_messages" in system_info:
                all_messages.extend(system_info["all_messages"])
    
    # Remove duplicates by converting to dict (preserving order in Python 3.7+)
    # Use qualified_name + key as unique identifier
    seen = {}
    unique_messages = []
    for msg in all_messages:
        msg_id = (msg.get('qualified_name', msg.get('schema_name')), str(msg.get('key')))
        if msg_id not in seen:
            seen[msg_id] = True
            unique_messages.append(msg)
    all_messages = unique_messages
    
    # Create a cache key based on message count and agent_name
    # Simple but effective: if message count unchanged, reuse cached result
    current_state = (len(all_messages), agent_name)
    cache_key = (len(all_messages), agent_name)
    
    # Check cache before rebuilding
    if use_cache and cache_key in _message_history_cache:
        return _message_history_cache[cache_key]
    
    # Extract role names for multirole adapters
    # For multirole adapters, recipients contain role names like "Buyer", "Merchant"
    # not adapter names like "ahoy"
    role_names = []
    if "roles" in social_state and social_state["roles"]:
        for role in social_state["roles"]:
            if isinstance(role, dict) and "name" in role:
                role_names.append(role["name"])
            else:
                role_names.append(str(role))
    
    # Filter to messages relevant to this adapter's roles (or agent if no roles)
    if role_names:
        # For multirole adapters: show ALL messages since the adapter is executing them all
        # Messages may be sent by these roles (sender field) or sent to them (recipients field)
        # For context, we need to show both incoming and outgoing messages
        filtered = [m for m in all_messages 
                   if (any(role in m.get('recipients', []) for role in role_names) or
                       any(role == m.get('sender') for role in role_names))]
    elif agent_name:
        # For single-role adapters: try filtering by agent_name (legacy support)
        filtered = [m for m in all_messages if agent_name in m.get('recipients', [])]
    else:
        # No filter: show all messages
        filtered = all_messages
    
    # Format message entries
    history_lines = ["=== MESSAGE HISTORY ==="]
    if not filtered:
        history_lines.append("\nNo message history available.")
    else:
        for idx, msg in enumerate(filtered[-max_history:], 1):
            schema = msg.get('schema_name', 'Unknown')
            sender = msg.get('sender', 'Unknown')
            recipients = ', '.join(msg.get('recipients', []))
            history_lines.append(f"\n{idx}. {schema} (from {sender} to {recipients})")
            
            payload = msg.get('payload', {})
            for key, val in payload.items():
                history_lines.append(f"   {key}: {val}")
    
    history_lines.append(f"\n=== END HISTORY ({len(filtered)} messages) ===")
    result = "\n".join(history_lines)
    
    # Cache the result
    if use_cache:
        _message_history_cache[cache_key] = result
    
    return result


# ============================================================================
# PROMPT BUILDING: Construct LLM prompts with context
# ============================================================================

def build_user_prompt(
    agent_name: str,
    social_state: Dict[str, Any],
    options: list,
    recent_event: Optional[dict] = None,
    examples: Optional[list] = None,
    include_history: bool = True,
    decision_count: int = 1,
    all_roles_list: Optional[List[Tuple[str, str]]] = None
) -> str:
    """Build a user prompt for the LLM including context and options.
    
    Args:
        agent_name: Name of the agent making the decision
        social_state: Extracted social state from adapter
        options: List of available message options
        recent_event: Optional recent event information
        examples: Optional example responses
        include_history: Whether to include message history
        decision_count: Which decision cycle this is (1-indexed)
    
    Returns:
        Formatted prompt ready for LLM processing
    """
    import json
    
    lines = [f"You are agent '{agent_name}'. Choose at most one option, or return null."]
    lines.append("Your role requires making decisions. When choosing an option, always provide values for all required parameters.")
    lines.append("")
    
    # Display all roles for multi-role scenarios
    if all_roles_list and len(all_roles_list) > 1:
        # Multi-role: show all (protocol, role) pairs
        roles_display = [f"{role} (in {protocol})" for protocol, role in all_roles_list]
        lines.append(f"Your roles: {', '.join(roles_display)}")
    else:
        # Single-role or fallback: use role names from social state
        role_names = social_state.get('roles', [])
        if role_names:
            roles_str = ', '.join(str(r) for r in role_names)
            lines.append(f"Roles: {roles_str}")
    
    # Add message history if requested (with caching optimization)
    if include_history and social_state:
        lines.append("")
        history = build_message_history_from_social_state(
            social_state, agent_name=agent_name, max_history=50, use_cache=True
        )
        lines.append(history)
    
    # Add available options with bound parameters for clarity
    lines.append("")
    lines.append("Options:")
    for opt in options:
        idx = opt.get('index', '?')
        schema = opt.get('schema_name', 'Unknown')
        missing = opt.get('missing_params', [])
        
        # Extract bound parameters for display
        partial = opt.get('partial')
        bindings_str = ""
        if partial and hasattr(partial, 'bindings'):
            bound_params = {k: v for k, v in partial.bindings.items() if v is not None}
            if bound_params:
                display_bindings = [f"{key}={value}" for key, value in bound_params.items()]
                if display_bindings:
                    bindings_str = f" [BOUND: {', '.join(display_bindings)}]"
        
        lines.append(f"{idx}) {schema}{bindings_str} - FILL ONLY: {missing}")
    
    lines.append("")
    
    # NOTE: Duplicate guidance sections removed from here
    # All parameter, tool, and format guidance is now in the SYSTEM PROMPT
    # This optimization reduces user prompt size by ~40%
    
    lines.append("Response format JSON:")
    lines.append('- To choose an option WITH parameters: {"choice": 0, "params": {"ID": "value", "item": "value"}, "tool_requests": []}')
    lines.append('- To decline all options: {"choice": null, "params": {}, "tool_requests": []}')
    lines.append("")
    
    # Only show examples on first decision to avoid redundancy
    if decision_count <= 1 and examples:
        lines.append("")
        lines.append("Examples:")
        for ex in examples:
            lines.append(json.dumps(ex))
    
    return "\n".join(lines)


# ============================================================================
# ID PARAMETER AUTO-GENERATION
# ============================================================================

def auto_generate_id_parameters(partial_message, logger_callback=None) -> Dict[str, Any]:
    """
    Automatically detect and generate unique IDs for ID-type parameters in a message.
    
    Inspects the message schema for parameters marked as 'key' (ID parameters) that are
    not yet bound, and generates unique UUIDs for them.
    
    Args:
        partial_message: A Partial message object with schema and bindings
        logger_callback: Optional function for logging: logger_callback(message)
    
    Returns:
        Dict of parameter_name -> generated_id for unbound ID parameters
    
    Example:
        If a message has an ID parameter that's unbound, returns:
        {"ID": "550e8400-e29b-41d4-a716-446655440000"}
    """
    def log_msg(msg):
        """Helper to log messages if callback provided."""
        if logger_callback:
            logger_callback(msg)
    
    generated_ids = {}
    
    # Check if the message schema has parameter information
    if not hasattr(partial_message, 'schema'):
        log_msg("No schema available for auto-ID generation")
        return generated_ids
    
    if not hasattr(partial_message.schema, 'parameters'):
        log_msg("Schema has no parameters attribute")
        return generated_ids
    
    # Iterate through schema parameters to find key (ID) parameters
    for param_name in partial_message.schema.parameters:
        param_info = partial_message.schema.parameters[param_name]
        
        # Check if this parameter is marked as 'key' (ID parameter)
        is_key_param = False
        if isinstance(param_info, dict):
            is_key_param = param_info.get('is_key', False)
        elif hasattr(param_info, 'is_key'):
            is_key_param = param_info.is_key
        
        # Also check parameter name conventions (contains 'ID')
        param_name_is_id = 'ID' in param_name.upper() or param_name.lower() in ['id', 'uuid']
        
        if is_key_param or param_name_is_id:
            # Check if parameter is not already bound
            if partial_message.bindings.get(param_name) is None:
                unique_id = str(uuid.uuid4())
                generated_ids[param_name] = unique_id
                log_msg(f"Auto-generated ID for parameter '{param_name}': {unique_id}")
    
    return generated_ids

