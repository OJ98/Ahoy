#!/usr/bin/env python3
"""
Minimal utility functions for the multi-agent system.
Provides: message history building, user prompt construction, and adapter shutdown.
"""

import asyncio
import os
from typing import Any, Dict, Optional


# ============================================================================
# PROMPT CONTENT STRINGS
# ============================================================================






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
            enhanced_prompt = f.read()
            if not enhanced_prompt.strip():
                raise ValueError(f"Requirements file '{requirements_file}' is empty")
            
            enhanced_prompt = f"You are a {agent_name} agent.\n\nThe user has communicated the requirements to be as follows: {enhanced_prompt}. The following is an explanation of the environment in which you operate: \n\n"

            # BSPL Protocol Explanation Strings
            bspl_highlevel_explanation = """
            You are participating in BSPL (Blindingly Simple Protocol Language) protocol enactments. 
            BSPL defines multi-agent protocols where:
            - Roles are named agents (e.g., Merchant, Buyer)
            - Messages are directed communication between roles with parameters marked as `out` (sender provides) or `in` (requires prior binding from other messages)
            - Parameters marked `key` identify protocol instances
            - You play one role and must track received messages to determine which messages you can legally send next
            - A message can only be sent when all its `in` parameters are bound by prior messages
            - When multiple messages are enabled, choose based on domain reasoning and the protocol's intended flow"""
            enhanced_prompt = enhanced_prompt + bspl_highlevel_explanation
 
            # Option Selection
            option_selection = """
            Your choice will directly determine what message gets SENT and what happens next:
            - The BOUND parameters shown above (in [BOUND: ...]) are already set and will be used
            - You only need to provide values for parameters marked in FILL ONLY
            - Your selection will trigger protocol actions based on the message type and parameters"""
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
            
            # TOOL USAGE GUIDANCE: Direct LLM to use tools for ID generation and memory
            tool_guidance = """
            AVAILABLE TOOLS FOR YOUR USE:
            You have two tools available to enhance your decision-making:

            1. **generate_unique_id** - Creates guaranteed-unique message IDs
            - Use this EVERY TIME you need a new message ID
            - Parameters: prefix (e.g., "RFQ", "ORDER") and purpose (what the message is for)
            - Returns a unique ID in format: PREFIX_HEXID_TIMESTAMP
            - This ensures no ID conflicts or parameter duplication errors
            
            When to use:
            - Sending a NEW message that requires a unique ID parameter
            - Exploring multiple options with different IDs
            - Never manually create IDs - always use this tool
            
            Example workflow:
            1. Decide you need to send a message with a new ID
            2. Request generate_unique_id with appropriate prefix and purpose
            3. Receive the generated ID
            4. Use that exact ID in your message parameters

            2. **save_state_to_memory** - Records important information for later recall
            - Use this to save constraints, decisions, or strategies you want to remember
            - Parameters: agent_name, key (name of what you're saving), value (the content)
            - Saved information can help you maintain consistency across decisions

            CRITICAL: Always use generate_unique_id for new message IDs - do not invent IDs yourself.
            This prevents parameter variation errors and duplicate message rejection."""
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
    
    # Add tool list
    lines.append("")
    lines.append("AVAILABLE TOOLS:")
    lines.append("1. **generate_unique_id** - Generates unique transaction IDs")
    lines.append("   - Input: {\"prefix\": \"RFQ\", \"purpose\": \"inquiry\"}")
    lines.append("   - Output: Unique ID like 'TXN_a1b2c3_1430'")
    lines.append("")
    lines.append("2. **save_state_to_memory** - Saves agent state/notes for later retrieval")
    lines.append("   - Input: {\"agent_name\": \"Agent\", \"key\": \"key_name\", \"value\": \"state_value\"}")
    lines.append("")
    
    # Add response formatting instructions
    lines.append("")
    lines.append("Response format JSON:")
    lines.append('- To choose an option WITH parameters: {"choice": 0, "params": {"ID": "value", "item": "value"}, "tool_requests": []}')
    lines.append('- To decline all options: {"choice": null, "params": {}, "tool_requests": []}')
    lines.append("- To request tools: include tool_requests array with {\"tool\": \"name\", \"args\": {...}}")
    lines.append("")
    lines.append("IMPORTANT: When requesting tools to generate parameters (like generate_unique_id for ID):")
    lines.append("1. Include the tool_requests array with your tool calls")
    lines.append("2. ALSO include placeholder values in params for those parameters")
    lines.append("   - For IDs: use params {\"ID\": \"PENDING_FROM_TOOL\", ...}")
    lines.append("   - The system will execute the tool and use the generated value")
    lines.append("3. If you request generate_unique_id, the returned ID will fill the ID parameter")
    lines.append("4. Provide values for ALL required parameters (both generated and manual)")
    lines.append("")
    lines.append("DECISION RULE: You must make a choice (do not use null) unless there is NO viable option.")
    
    # Add examples if provided
    if examples:
        lines.append("")
        lines.append("Examples:")
        for ex in examples:
            lines.append(json.dumps(ex))
    
    return "\n".join(lines)
