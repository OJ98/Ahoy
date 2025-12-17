#!/usr/bin/env python3
"""
Minimal utility functions for the multi-agent system.
Provides: message history building, user prompt construction, and adapter shutdown.
"""

import asyncio
import os
from typing import Any, Dict, Optional


# ============================================================================
# SYSTEM PROMPT BUILDING
# ============================================================================

def build_system_prompt(agent_name: str, requirements_file: str = "input.txt") -> str:
    """
    Build a system prompt for the agent by reading from a text file.
    
    Reads user instructions and constraints from a text file to use as the system prompt.
    
    Args:
        agent_name: Name of the agent (e.g., "Buyer", "Seller")
        requirements_file: Path to the text file with requirements/constraints (default: "input.txt")
        The file should contain the agent's instructions and constraints.
    
    Returns:
        System prompt string for the LLM (file contents)
    
    Raises:
        FileNotFoundError: If the requirements file cannot be found
    """
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                raise ValueError(f"Requirements file '{requirements_file}' is empty")
            return content
    except FileNotFoundError:
        raise FileNotFoundError(
            f"System prompt file '{requirements_file}' not found. "
            f"Please create it with your agent's instructions and constraints."
        )


# ============================================================================
# ADAPTER MANAGEMENT: Graceful shutdown
# ============================================================================

async def shutdown_watcher(adapter, stop_path: str = ".stop_signal"):
    """Watch for stop signal file and gracefully shut down the adapter."""
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
    max_history: int = 10
) -> str:
    """Build a formatted history of past messages from social state.
    
    Constructs a human-readable summary of recent messages for LLM context,
    optionally filtered to messages sent to a specific agent.
    
    Args:
        social_state: Extracted social state dictionary
        agent_name: Optional agent name to filter by
        max_history: Maximum number of recent messages to include
    
    Returns:
        Formatted message history as a string
    """
    history_lines = ["=== PAST MESSAGE HISTORY ==="]
    
    # Extract all messages from social state systems
    all_messages = []
    if "systems" in social_state:
        for system_info in social_state["systems"].values():
            if "all_messages" in system_info:
                all_messages.extend(system_info["all_messages"])
    
    # Filter to messages sent to agent if specified
    if agent_name:
        filtered = [m for m in all_messages if agent_name in m.get('recipients', [])]
    else:
        filtered = all_messages
    
    # Format message entries
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
    return "\n".join(history_lines)


# ============================================================================
# PROMPT BUILDING: Construct LLM prompts with context
# ============================================================================

def build_user_prompt(
    agent_name: str,
    social_state: Dict[str, Any],
    options: list,
    recent_event: Optional[dict] = None,
    examples: Optional[list] = None,
    include_history: bool = True
) -> str:
    """Build a user prompt for the LLM including context and options.
    
    Args:
        agent_name: Name of the agent making the decision
        social_state: Extracted social state from adapter
        options: List of available message options
        recent_event: Optional recent event information
        examples: Optional example responses
        include_history: Whether to include message history
    
    Returns:
        Formatted prompt ready for LLM processing
    """
    import json
    
    lines = [f"You are agent '{agent_name}'. Choose at most one option, or return null."]
    lines.append("Your role requires making decisions. When choosing an option, always provide values for all required parameters.")
    lines.append("")
    role_names = social_state.get('roles', [])
    if role_names:
        roles_str = ', '.join(str(r) for r in role_names)
        lines.append(f"Roles: {roles_str}")
    
    # Add message history if requested
    if include_history and social_state:
        lines.append("")
        history = build_message_history_from_social_state(
            social_state, agent_name=agent_name, max_history=10
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
    
    # Add critical note about option selection
    lines.append("")
    lines.append("⚠️  CRITICAL: Your choice will directly determine what message gets SENT and what happens next:")
    lines.append("- The BOUND parameters shown above (in [BOUND: ...]) are already set and will be used")
    lines.append("- You only need to provide values for parameters marked in FILL ONLY")
    lines.append("- Your selection will trigger protocol actions based on the message type and parameters")
    
    # Add critical parameter rules
    lines.append("")
    lines.append("**CRITICAL PARAMETER RULES:**")
    lines.append("1. Parameters marked [BOUND: ...] are ALREADY SET and should NOT be provided by you")
    lines.append("2. Parameters marked 'FILL ONLY: [...]' are the ONLY ones you should provide values for")
    lines.append("3. If you choose an option, provide values for ALL parameters in the FILL ONLY list")
    lines.append("4. Do not provide values for BOUND parameters - they will cause errors")
    lines.append("5. Either provide all required FILL ONLY params, or choose null.")
    
    # Add tool guidance
    lines.append("")
    lines.append("AVAILABLE TOOLS:")
    lines.append("1. **generate_unique_id** - Generates unique transaction IDs")
    lines.append("   - Input: {\"prefix\": \"RFQ\", \"purpose\": \"inquiry\"}")
    lines.append("   - Output: Unique ID like 'TXN_a1b2c3_1430'")
    lines.append("")
    lines.append("2. **save_state_to_memory** - Saves agent state/notes for later retrieval")
    lines.append("   - Input: {\"agent_name\": \"Agent\", \"key\": \"key_name\", \"value\": \"state_value\"}")
    lines.append("")
    
    # Add response format
    lines.append("")
    lines.append("Response format JSON:")
    lines.append('- To choose an option WITH parameters: {"choice": 0, "params": {"ID": "value", "item": "value"}, "tool_requests": []}')
    lines.append('- To decline all options: {"choice": null, "params": {}, "tool_requests": []}')
    lines.append("- To request tools: include tool_requests array with {\"tool\": \"name\", \"args\": {...}}")
    lines.append("")
    lines.append("DECISION RULE: You must make a choice (do not use null) unless there is NO viable option.")
    
    # Add examples if provided
    if examples:
        lines.append("")
        lines.append("Examples:")
        for ex in examples:
            lines.append(json.dumps(ex))
    
    return "\n".join(lines)
