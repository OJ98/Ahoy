#!/usr/bin/env python3
"""
Minimal utility functions for the multi-agent system.
Provides: message history building, user prompt construction, and adapter shutdown.
"""

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Union, List, Tuple

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_log_dir(project_root: Path, log_filename: str = None) -> Path:
    """
    Determine log directory based on ablation mode and log type.
    
    For ablation studies:
    - generic_agent_debug logs go to ablation/baseline{X}_logs/
    - All other logs (wrapper.log, merchant.log, etc.) go to logs/
    
    Args:
        project_root: Path to project root directory
        log_filename: Optional log filename to check type (e.g., "generic_agent_debug_*.log")
    
    Returns:
        Path to appropriate log directory
    """
    # Check for ablation mode
    ablation_mode = os.getenv("ABLATION_MODE", "").lower()
    
    # Only redirect generic_agent_debug logs to ablation folder
    redirect_to_ablation = (
        ablation_mode and 
        log_filename and 
        "generic_agent_debug" in log_filename
    )
    
    if redirect_to_ablation:
        # Convert ablation mode to log directory name
        # e.g., "baseline0_full" -> "baseline0_logs"
        baseline_num = ablation_mode.split('_')[0].replace('baseline', '')
        log_dir_name = f"baseline{baseline_num}_logs"
        log_dir = project_root / "ablation" / log_dir_name
    else:
        # Standard logging to main logs folder
        log_dir = project_root / "logs"
    
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

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
# PROTOCOL DEFINITIONS: Include BSPL files in system prompt
# ============================================================================

def _include_protocol_definitions() -> str:
    """
    Load all BSPL protocol definitions from the protocols folder.
    
    Returns:
        Formatted string with all protocol definitions for inclusion in system prompt
    """
    from pathlib import Path
    
    protocols_dir = Path(__file__).resolve().parent.parent / "protocols"
    
    protocol_section = "\n\n" + "=" * 70 + "\n"
    protocol_section += "PROTOCOL DEFINITIONS (BSPL specs with inline message explanations):\n"
    protocol_section += "=" * 70 + "\n\n"
    
    bspl_files = sorted(protocols_dir.glob("*.bspl"))
    
    if not bspl_files:
        return protocol_section + "(No BSPL protocol files found)\n"
    
    for bspl_file in bspl_files:
        try:
            with open(bspl_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                protocol_name = bspl_file.stem  # filename without extension
                protocol_section += f"\n--- {protocol_name.upper()} PROTOCOL ---\n\n"
                protocol_section += content + "\n"
        except Exception as e:
            # Gracefully skip files that can't be read
            protocol_section += f"\n(Error reading {bspl_file.name}: {e})\n"
    
    protocol_section += "\n" + "=" * 70 + "\n"
    return protocol_section


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
            user_goal = f.read()
            if not user_goal.strip():
                raise ValueError(f"Requirements file '{requirements_file}' is empty")
            
            # Build agent introduction
            if is_multi_protocol:
                agents_str = ", ".join(agent_names_list)
                system_prompt = f"You are enacting MULTIPLE roles: {agents_str}.\n\n"
            else:
                system_prompt = f"You are a {agent_names_list[0]} agent.\n\n"
            
            # Connect user goal to protocol interaction
            system_prompt += f"Your user wants you to fulfill the goal described in input.txt contents:\n{user_goal}\n\n"
            system_prompt += "To accomplish this goal, you may need to interact with other agents on the basis of interaction protocols.\n\n"
            system_prompt += "The following is an explanation of the environment in which you operate:\n\n"

            # BSPL Protocol Explanation Strings (optimized for efficiency and clarity)
            bspl_highlevel_explanation = """
                BSPL defines multiagent protocols where agents play roles and coordinate via information causality.

                PARAMETER ADORNMENTS (three types):
                1. **in** (Causal): Must already know from prior messages. Information provided from previous messages in the protocol.
                2. **out** (Generation): You generate this binding; it appears once per enactment, creating mutual exclusion. Your role generates unique values for protocol instances.
                3. **nil** (Negative): Must NOT know this binding. Used for mutually exclusive paths where an agent cannot act until certain information remains unknown.

                Key parameters identify protocol instances. Messages are ordered by information flow according to causal dependencies.
            """
            
            system_prompt = system_prompt + bspl_highlevel_explanation
 
            # Consolidated Option Selection & Parameter Guidance
            option_selection = """
            EXTERNAL EVENTS: External events represent new tasks that occur during protocol enactment. Each external event is treated as a separate transaction and may trigger new message sequences according to the protocol.

            PARAMETER RULES:
            - [in: ...] AUTO-PROVIDED from prior messages: do NOT provide
            - [out: ...] REQUIRED: you must provide all
            - [nil: ...] OPTIONAL: may omit
            IDs auto-generated; do NOT create them.

            TOOLS: save_state_to_memory(agent_name, key, value)
            
            RESPONSE: {"choice": 0|null, "params": {...}, "tool_requests": [{"tool": "...", "args": {...}}]}

            RULE: Choose if viable. Null only if no options.
            """
            system_prompt = system_prompt + option_selection
            
            # Include all BSPL protocol definitions from the protocols folder
            system_prompt += _include_protocol_definitions()
            
            return system_prompt
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
    all_roles_list: Optional[List[Tuple[str, str]]] = None,
    pending_event_context: Optional[str] = None
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
        pending_event_context: Optional context about pending external events to include in prompt
    
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
    elif all_roles_list and len(all_roles_list) == 1:
        # Single-role: show the specific role this agent plays
        protocol, role = all_roles_list[0]
        lines.append(f"Role: {role} (in {protocol})")
    else:
        # Fallback: use role names from social state
        role_names = social_state.get('roles', [])
        if role_names:
            roles_str = ', '.join(str(r) for r in role_names)
            lines.append(f"Roles: {roles_str}")

    
    # Add pending external events context if available
    if pending_event_context:
        lines.append("")
        lines.append("=== PENDING EXTERNAL EVENTS ===")
        lines.append(pending_event_context)
        lines.append("=== END PENDING EVENTS ===")
    else:
        # No events, but make it explicit in the prompt so LLM knows
        lines.append("")
        lines.append("(No pending external events at this time)")
    
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
        required = opt.get('missing_params', [])
        optional = opt.get('optional_params', [])
        
        # Extract bound parameters for display
        partial = opt.get('partial')
        bindings_str = ""
        if partial and hasattr(partial, 'bindings'):
            bound_params = {k: v for k, v in partial.bindings.items() if v is not None}
            if bound_params:
                display_bindings = [f"{key}={value}" for key, value in bound_params.items()]
                if display_bindings:
                    bindings_str = f" [in: {', '.join(display_bindings)}]"
        
        # Format parameter display with required and optional separated
        if optional:
            param_str = f"out: {required} | nil: {optional}"
        else:
            param_str = f"out: {required}"
        lines.append(f"{idx}) {schema}{bindings_str} - {param_str}")
    
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
# CUSTOM EVENT-FOCUSED PROMPT BUILDING
# ============================================================================

def build_custom_event_user_prompt(
    agent_name: str,
    social_state: Dict[str, Any],
    options: list,
    events: List[Dict[str, Any]],
    all_roles_list: Optional[List[Tuple[str, str]]] = None,
    decision_count: int = 1
) -> str:
    """
    Build a user prompt for handling custom external events.
    
    **CRITICAL**: Uses the EXACT SAME structure as build_user_prompt to prevent LLM confusion.
    The ONLY difference is that external events are highlighted prominently.
    
    This ensures the LLM sees a consistent format whether or not events are present:
    - Same header wording
    - Same role display format
    - Same message history section
    - Same options formatting
    - Same response format examples
    
    Args:
        agent_name: Name of the agent making the decision
        social_state: Extracted social state from adapter (contains message history)
        options: List of available message options from adapter
        events: List of event dicts, each with 'message', 'metadata', 'priority'
        all_roles_list: Optional list of (protocol, role) tuples for multi-role agents
        decision_count: Which decision cycle this is (1-indexed)
    
    Returns:
        Formatted prompt ready for LLM processing (identical structure to build_user_prompt)
    """
    lines = []
    
    # === IDENTICAL HEADER to build_user_prompt ===
    lines.append(f"You are agent '{agent_name}'. Choose at most one option, or return null.")
    lines.append("Your role requires making decisions. When choosing an option, always provide values for all required parameters.")
    lines.append("")
    
    # === IDENTICAL ROLE DISPLAY to build_user_prompt ===
    if all_roles_list and len(all_roles_list) > 1:
        roles_display = [f"{role} (in {protocol})" for protocol, role in all_roles_list]
        lines.append(f"Your roles: {', '.join(roles_display)}")
    elif all_roles_list and len(all_roles_list) == 1:
        protocol, role = all_roles_list[0]
        lines.append(f"Role: {role} (in {protocol})")
    else:
        role_names = social_state.get('roles', [])
        if role_names:
            roles_str = ', '.join(str(r) for r in role_names)
            lines.append(f"Roles: {roles_str}")
    
    lines.append("")
    
    # === PROMINENT EXTERNAL EVENTS (only addition vs build_user_prompt) ===
    lines.append("=" * 80)
    lines.append("EXTERNAL EVENTS REQUIRING YOUR ACTION:")
    lines.append("=" * 80)
    lines.append("")
    
    for idx, event in enumerate(events, 1):
        lines.append(f"Event #{idx}: {event.get('message', 'Unknown event')}")
        lines.append(f"  Priority: {event.get('priority', 'normal')}")
        
        metadata = event.get('metadata', {})
        if metadata:
            lines.append("  Details:")
            for key, value in metadata.items():
                lines.append(f"    • {key}: {value}")
        lines.append("")
    
    # === IDENTICAL MESSAGE HISTORY to build_user_prompt ===
    lines.append("=" * 80)
    lines.append("MESSAGE HISTORY:")
    lines.append("=" * 80)
    if social_state:
        history = build_message_history_from_social_state(
            social_state, agent_name=agent_name, max_history=50, use_cache=True
        )
        lines.append(history)
    else:
        lines.append("No message history yet - this is the first message.")
    
    lines.append("")
    
    # === IDENTICAL OPTIONS FORMAT to build_user_prompt ===
    lines.append("Options:")
    for opt in options:
        idx = opt.get('index', '?')
        schema = opt.get('schema_name', 'Unknown')
        missing = opt.get('missing_params', [])
        
        partial = opt.get('partial')
        bindings_str = ""
        if partial and hasattr(partial, 'bindings'):
            bound_params = {k: v for k, v in partial.bindings.items() if v is not None}
            if bound_params:
                display_bindings = [f"{key}={value}" for key, value in bound_params.items()]
                if display_bindings:
                    bindings_str = f" [in: {', '.join(display_bindings)}]"
        
        lines.append(f"{idx}) {schema}{bindings_str} - {param_str}")
    
    lines.append("")
    
    # === IDENTICAL RESPONSE FORMAT to build_user_prompt ===
    lines.append("Response format JSON:")
    lines.append('- To choose an option WITH parameters: {"choice": 0, "params": {"ID": "value", "item": "value"}, "tool_requests": []}')
    lines.append('- To decline all options: {"choice": null, "params": {}, "tool_requests": []}')
    
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

