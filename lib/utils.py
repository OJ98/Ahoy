#!/usr/bin/env python3
"""
Minimal utility functions for the multi-agent system.
Provides: message history building, user prompt construction, and adapter shutdown.
"""

import asyncio
import os
import uuid
from typing import Any, Dict, Optional, Union, List


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
 
            # Option Selection
            option_selection = """
            Your choice will directly determine what message gets SENT and what happens next:
            - The BOUND parameters shown above (in [BOUND: ...]) are already set and will be used
            - You only need to provide values for parameters marked in FILL ONLY
            - Your selection will trigger protocol actions based on the message type and parameters
            
            IMPORTANT: When multiple message options are available, carefully consider which ones you need to send:
            - Do NOT assume you only need to send one message type
            - Some protocols require sending multiple different message types to make progress
            - If the protocol needs both message A and message B to be sent by your role, send BOTH (in separate decisions)
            - Only return null if NO viable messages are available right now"""
            enhanced_prompt = enhanced_prompt + option_selection

            # Critical Parameter Rules
            parameter_rules = """
            **CRITICAL PARAMETER RULES:**
            1. Parameters marked [BOUND: ...] are ALREADY SET and should NOT be provided by you
            2. Parameters marked 'FILL ONLY: [...]' are the ONLY ones you should provide values for
            3. If you choose an option, provide values for ALL parameters in the FILL ONLY list
            4. Do not provide values for BOUND parameters - they will cause errors
            5. Either provide all required FILL ONLY params, or choose null."""
            enhanced_prompt = enhanced_prompt + parameter_rules
            
            # TOOL USAGE GUIDANCE
            tool_guidance = """
            AVAILABLE TOOLS FOR YOUR USE:
            
            1. **save_state_to_memory** - Records important information for later recall
            - Use this to save constraints, decisions, or strategies you want to remember
            - Parameters: agent_name, key (name of what you're saving), value (the content)
            - Saved information can help you maintain consistency across decisions

            ID MANAGEMENT:
            - The system AUTOMATICALLY generates unique IDs for any ID parameters (marked as 'key' in the protocol)
            - You DO NOT need to provide or generate IDs - they will be created automatically for you
            - Simply select the option you want, and any required IDs will be generated and bound automatically
            - Only provide IDs if they are explicitly required by the protocol as 'FILL ONLY' parameters
            - Required non-ID parameters (orderID, itemID, etc.) should come from user input or protocol message history"""
            enhanced_prompt = enhanced_prompt + tool_guidance
            

            # Exploration Strategy (Maybe the user specifies this?)
            # exploration_strategy = """
            # EXPLORATION STRATEGY
            # When you receive response options (quotes, offers, proposals, or any message variants):
            # - DO NOT immediately reject/dismiss or accept after seeing just one option
            # - WAIT to see multiple options before making ANY final decision (accept OR reject)
            # - COMPARE all available alternatives before deciding to accept, reject, or counter-offer
            # - Only accept if: (1) multiple options have arrived AND (2) this option is the best available
            # - Only reject if: (1) multiple options have arrived AND (2) this option is clearly inferior
            # - If unsure, ASK FOR MORE INFORMATION rather than accepting or rejecting

            # Consequences of premature decisions:
            # - Once you accept/reject/dismiss an option with a specific ID, you may not be able to revert that decision
            # - Accepting too early removes your ability to negotiate or wait for better options
            # - Rejecting too early removes your alternatives when better options don't arrive
            # - Protocol state may prevent you from changing a decision after it's made

            # Strategy:
            # 1. On first option received: Do NOT accept OR reject immediately - wait for competing options
            # 2. When multiple options arrive: Compare them all before deciding
            # 3. Select the best option or request additional information
            # 4. Only accept if the option is clearly the best available even after seeing alternatives
            # 5. Only reject if the option is clearly unacceptable even with alternatives available

            # This approach maximizes your bargaining power and prevents hasty decisions.
            # """
            # enhanced_prompt = enhanced_prompt + exploration_strategy

            # Logging Reminder
            logging_reminder = """
            AGENT DECISION LOGGING:
            You have access to the save_state_to_memory tool which you should use to create an audit trail:

            1. BEFORE COMMITTING TO A DECISION:
            Use save_state_to_memory with:
            - agent_name: Your role (e.g., "Buyer")
            - key: "enactment_decision_intent"
            - value: JSON with your decision details including:
                {"choice_made": "Option X: [message type]", "reason": "[why this choice]", "will_affect": "[impact on protocol]"}

            2. EXAMPLE (Purchase Protocol):
            If you decide to accept an RFQ with price $12:
            save_state_to_memory("Buyer", "enactment_decision_intent", '{"choice_made": "Option 2: Purchase/accept", "reason": "Lowest price at $12", "will_affect": "Seller will receive acceptance, Shipper will deliver"}')

            EXAMPLE (Any Other Protocol):
            If you decide to send any message:
            save_state_to_memory("YourRole", "enactment_decision_intent", '{"choice_made": "Option 1: [Your Message Type]", "reason": "[Your reason]", "will_affect": "[Protocol impact]"}')

            3. AFTER SENDING THE MESSAGE:
            Record what actually happened with:
            - agent_name: Your role
            - key: "message_execution_log"
            - value: JSON with execution details

            Using these tools creates a persistent record of your decisions and actions, enabling verification that what you intended matched what actually executed."""

            enhanced_prompt = enhanced_prompt + logging_reminder
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
    history_lines = ["=== MESSAGE HISTORY ==="]
    
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
    
    # Add tool list
    lines.append("")
    lines.append("AVAILABLE TOOLS:")
    lines.append("1. **save_state_to_memory** - Saves agent state/notes for later retrieval")
    lines.append("   - Input: {\"agent_name\": \"Agent\", \"key\": \"key_name\", \"value\": \"state_value\"}")
    lines.append("")
    lines.append("NOTE ON ID PARAMETERS:")
    lines.append("- The system automatically generates and binds unique IDs for 'key' parameters")
    lines.append("- You do NOT need to provide IDs - they will be created automatically")
    lines.append("- Simply select your desired option and the system handles ID generation")
    lines.append("")
    
    # Add response formatting instructions
    lines.append("")
    lines.append("Response format JSON:")
    lines.append('- To choose an option WITH parameters: {"choice": 0, "params": {"ID": "value", "item": "value"}, "tool_requests": []}')
    lines.append('- To decline all options: {"choice": null, "params": {}, "tool_requests": []}')
    lines.append("- To request tools: include tool_requests array with {\"tool\": \"name\", \"args\": {...}}")
    lines.append("")
    lines.append("DECISION RULE: Always choose an option if you have viable parameters.")
    lines.append("Use values from the user input, protocol history, or reasonable defaults.")
    lines.append("Return null only if there is NO viable option at all.")
    lines.append("")
    
    # Add examples if provided
    if examples:
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

