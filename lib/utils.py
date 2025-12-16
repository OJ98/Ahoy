#!/usr/bin/env python3
"""
Utility functions for the multi-agent system.
Provides adapter shutdown, message history building, prompt construction, and
requirement gathering for LLM-driven agent decision-making.
"""

import asyncio
import json
import os
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .llm_client import LLMClient


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
        agent_name: Optional agent name to filter by (show only messages to this agent)
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
    
    # Add available options
    lines.append("")
    lines.append("Options:")
    for opt in options:
        idx = opt.get('index', '?')
        schema = opt.get('schema_name', 'Unknown')
        missing = opt.get('missing_params', [])
        lines.append(f"{idx}) {schema} - REQUIRED params: {missing}")
    
    # Add critical instruction
    lines.append("")
    lines.append("**CRITICAL: If you choose an option, you MUST provide values for ALL required parameters.**")
    lines.append("**Do not return incomplete params. Either send with all required params, or choose null.**")
    
    # Add optional tool guidance
    lines.append("")
    lines.append("OPTIONAL TOOL REQUESTS (Protocol-Agnostic):")
    lines.append("You can request tools to generate parameters by including tool requests in your JSON response:")
    lines.append("")
    lines.append("AVAILABLE TOOLS:")
    lines.append("1. **generate_unique_id** - Generates unique transaction IDs")
    lines.append("   - Input: {\"prefix\": \"RFQ\", \"purpose\": \"pen inquiry\"}")
    lines.append("   - Output: Unique ID like 'TXN_a1b2c3_1430'")
    lines.append("")
    lines.append("2. **save_state_to_memory** - Saves agent state/notes for later retrieval")
    lines.append("   - Input: {\"agent_name\": \"Buyer\", \"key\": \"sent_messages\", \"value\": \"<JSON string with message tracking>\"}")
    lines.append("   - Use for: Recording every message you send to prevent duplicates")
    lines.append("")
    lines.append("DUPLICATE PREVENTION - CRITICAL:")
    lines.append("To prevent sending the same message twice with different parameters:")
    lines.append("1. Before sending a message, use save_state_to_memory to record it")
    lines.append("   - Key: 'sent_messages'")
    lines.append("   - Value: JSON string: {\"message_type\": \"accept\", \"ID\": \"RFQ_001\", \"timestamp\": \"ISO8601\"}")
    lines.append("2. NEVER send the same message (same type + ID) with different parameter values")
    lines.append("3. Each message you send must be unique in its identifying characteristics")
    lines.append("4. If you already sent this message, choose null instead of resending it")
    lines.append("")
    lines.append("PARAMETER FILLING GUIDANCE:")
    lines.append("For required parameters not in the tool list, provide reasonable values:")
    lines.append("- **address**: Delivery address (use: 'Raleigh, NC 27606')")
    lines.append("- **resp**: Confirmation/response text (e.g., 'Confirmed', 'Proceeding with shipment')")
    lines.append("- **outcome**: Result reason (e.g., 'Price acceptable', 'Out of budget')")
    lines.append("- **satisfaction**: Quality feedback (e.g., 'Product meets requirements', 'Satisfactory delivery')")
    lines.append("")
    lines.append("HOW TO REQUEST TOOLS:")
    lines.append("Include tool_requests in your JSON response like this:")
    lines.append('{\"choice\": 0, \"params\": {...}, \"needs_tools\": true, \"tool_requests\": [{\"tool\": \"generate_unique_id\", \"args\": {\"prefix\": \"RFQ\", \"purpose\": \"inquiry\"}}, {\"tool\": \"save_state_to_memory\", \"args\": {\"agent_name\": \"Buyer\", \"key\": \"sent_messages\", \"value\": \"{\\"message_type\\": \\"rfq\\", \\"ID\\": \\"TBD\\"}\"}}]}')
    lines.append("")
    lines.append("The system will execute your tool requests and call you again with the results.")
    lines.append("**IMPORTANT: Always return your choice and all required parameters as JSON.**")
    lines.append("**For ID parameters: Request the generate_unique_id tool to ensure unique IDs across runs.**")
    
    # Add event context if available
    if recent_event:
        added = None
        if isinstance(recent_event, dict):
            added = recent_event.get("added")
        elif hasattr(recent_event, 'added'):
            added = recent_event.added
        
        if added:
            lines.append(f"Recent added count: {len(added)}")
    
    # Add response format specification
    lines.append("")
    lines.append("Response format JSON:")
    lines.append('- To choose an option WITH its required parameters: {"choice": 0, "params": {"ID": "value", "item": "value"}}')
    lines.append('- To decline all options: {"choice": null, "params": {}}')
    lines.append("")
    lines.append("DECISION RULE: You must make a choice (do not use null) unless there is NO viable option.")
    lines.append("For missing parameters, make reasonable assumptions based on context and create placeholder values.")
    lines.append("")
    lines.append("INITIALIZATION CONTEXT: If this is the start of a transaction with no prior history,")
    lines.append("use realistic but generic placeholder values (e.g., standard item names, typical IDs).")
    lines.append("The system will evolve from these initial values as stakeholders provide feedback.")
    lines.append("")
    lines.append("MULTI-OPTION EXPLORATION: To explore all available options:")
    lines.append("- Send messages with DIFFERENT transaction/inquiry IDs to solicit multiple responses")
    lines.append("- Example: Send with ID='OPTION_001', then later with ID='OPTION_002' to compare")
    lines.append("- This strategy works across any protocol to gather alternative proposals")
    lines.append("- Once you have multiple responses, evaluate and select the best option")
    
    # Add examples if provided
    if examples:
        lines.append("")
        lines.append("Examples:")
        for ex in examples:
            lines.append(json.dumps(ex))
    
    return "\n".join(lines)


# ============================================================================
# REQUIREMENT GATHERING: Interactive LLM-driven requirement collection
# ============================================================================

def _collect_user_input(prompt_text: Optional[str] = None) -> str:
    """Collect multi-line user input until 'done' is entered."""
    if prompt_text:
        print(prompt_text)
    
    lines = []
    while True:
        try:
            line = input()
            if line.strip().lower() == "done":
                break
            lines.append(line)
        except EOFError:
            break
    
    return "\n".join(lines).strip()


def _extract_role_from_response(
    response: str,
    available_roles: Optional[list] = None
) -> Optional[str]:
    """Extract inferred role from LLM response text.
    
    Looks for "ROLE:" marker in response, falling back to substring matching
    against available roles if marker not found.
    """
    # Try to extract from ROLE: marker
    if "ROLE:" in response:
        role_section = response.split("ROLE:")[1].split("\n")[0].strip()
        extracted = role_section.split()[0] if role_section else None
    else:
        extracted = None
    
    if not extracted and available_roles:
        # Fallback: search for role mentions
        available_strs = [str(r) for r in available_roles]
        for role in available_strs:
            if role.lower() in response.lower():
                extracted = role
                break
    
    return extracted


def _extract_system_prompt_from_response(response: str) -> str:
    """Extract system prompt from LLM response text.
    
    Looks for "SYSTEM_PROMPT:" marker, otherwise uses entire response.
    Appends critical requirement about parameter binding.
    """
    if "SYSTEM_PROMPT:" in response:
        prompt = response.split("SYSTEM_PROMPT:")[1].strip()
    else:
        prompt = response
    
    # Append critical requirement
    critical = "\n\n**Critical Requirement:**\nWhen selecting messages, you MUST ALWAYS provide explicit parameter values for all parameters set to None."
    return prompt + critical


async def _call_llm_for_analysis(
    client: "LLMClient",
    prompt: str,
    timeout: float,
    max_tokens: int,
    ui_callback: Optional[Any] = None,
    action: str = "analyzing"
) -> str:
    """Call LLM with timeout, handling errors gracefully."""
    from .llm_client import call_llm_with_timeout
    
    if ui_callback:
        ui_callback.processing_in_background(action)
    
    try:
        return await call_llm_with_timeout(client, prompt, timeout=timeout, max_tokens=max_tokens)
    except asyncio.TimeoutError:
        return f"[Timeout] Fallback: {prompt[:100]}..."


async def _build_system_prompt_from_conversation(
    client: "LLMClient",
    conversation: list,
    available_roles: Optional[list] = None,
    max_tokens: int = 1000,
    timeout: float = 30.0,
    ui_callback: Optional[Any] = None,
    logger_callback: Optional[Any] = None
) -> Tuple[Optional[str], str]:
    """Generate system prompt from multi-turn conversation history.
    
    Uses LLM to synthesize all requirements gathered during conversation
    into a coherent system prompt with inferred agent role.
    
    Args:
        client: LLM client instance
        conversation: List of {"role": "user"|"assistant", "content": "..."} messages
        available_roles: List of valid roles for role inference
        max_tokens: Max tokens for LLM response
        timeout: Timeout for LLM call
        ui_callback: Optional UI callback for display
        logger_callback: Optional logging callback
    
    Returns:
        Tuple of (inferred_role, system_prompt)
    """
    def log_msg(msg, level='debug'):
        if logger_callback:
            logger_callback(msg, level)
    
    # Build role context string
    roles_str = ', '.join(str(r) for r in available_roles) if available_roles else "any role"
    
    # Construct the final system prompt generation prompt
    final_prompt = f"""Based on all requirements:

1. Identify the agent role (must be one of: {roles_str})
2. Generate system prompt with:
   - Core mission
   - Decision guidelines
   - Constraints
   - Behavioral standards
   - Role interactions
   - ID parameter requirement

Format:
ROLE: <role_name>
SYSTEM_PROMPT: <prompt>"""
    
    # Add to conversation history
    conversation.append({"role": "user", "content": final_prompt})
    
    # Format conversation for logging
    full_conversation = "\n\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in conversation
    )
    
    log_msg(f"{'='*80}")
    log_msg(f"FINAL SYSTEM PROMPT GENERATION REQUEST")
    log_msg(f"{'='*80}")
    log_msg(full_conversation)
    log_msg(f"{'='*80}")
    
    # Call LLM to generate final system prompt
    final = await _call_llm_for_analysis(
        client, full_conversation, timeout, max_tokens, ui_callback, "generating system prompt"
    )
    
    log_msg(f"\n{'='*80}")
    log_msg(f"FINAL SYSTEM PROMPT GENERATION RESPONSE")
    log_msg(f"{'='*80}")
    log_msg(final)
    log_msg(f"{'='*80}\n")
    
    # Extract role and system prompt from response
    inferred_role = _extract_role_from_response(final, available_roles)
    system_prompt = _extract_system_prompt_from_response(final)
    
    return inferred_role, system_prompt


async def _analyze_requirements(
    client: "LLMClient",
    user_requirements: str,
    available_roles: Optional[list] = None,
    max_tokens: int = 1000,
    timeout: float = 30.0,
    ui_callback: Optional[Any] = None,
    logger_callback: Optional[Any] = None
) -> Tuple[str, list]:
    """Analyze user requirements and extract key information.
    
    Performs initial LLM analysis to identify priorities, guidelines,
    and decision criteria from raw user input.
    
    Args:
        client: LLM client instance
        user_requirements: Raw requirements text from user
        available_roles: Optional list of available roles for context
        max_tokens: Max tokens for LLM response
        timeout: Timeout for LLM call
        ui_callback: Optional UI callback
        logger_callback: Optional logging callback
    
    Returns:
        Tuple of (analysis_text, conversation_list)
    """
    def log_msg(msg, level='debug'):
        if logger_callback:
            logger_callback(msg, level)
    
    # Build role context
    role_context = ""
    if available_roles:
        roles_str = ', '.join(str(r) for r in available_roles)
        role_context = f"\n\nAvailable roles: {roles_str}. Infer the best match."
    
    # Construct analysis prompt
    analysis_prompt = f"""Requirements: {user_requirements}{role_context}

Analyze and:
1. Infer agent role
2. Identify priorities
3. Extract behavioral guidelines
4. Note decision criteria"""
    
    log_msg(f"{'='*80}")
    log_msg(f"REQUIREMENT ANALYSIS PROMPT")
    log_msg(f"{'='*80}")
    log_msg(analysis_prompt)
    log_msg(f"{'='*80}")
    
    # Call LLM for analysis
    analysis = await _call_llm_for_analysis(
        client, analysis_prompt, timeout, max_tokens, ui_callback, "analyzing requirements"
    )
    
    log_msg(f"\n{'='*80}")
    log_msg(f"REQUIREMENT ANALYSIS RESPONSE")
    log_msg(f"{'='*80}")
    log_msg(analysis)
    log_msg(f"{'='*80}\n")
    
    # Initialize conversation with this exchange
    conversation = [
        {"role": "user", "content": analysis_prompt},
        {"role": "assistant", "content": analysis}
    ]
    
    return analysis, conversation


async def gather_requirements_from_user(
    client: "LLMClient",
    available_roles: Optional[list] = None,
    context: str = "",
    *,
    max_tokens: int = 1000,
    timeout: float = 30.0,
    ui_callback: Optional[Any] = None,
    logger_callback: Optional[Any] = None
) -> Tuple[Optional[str], str]:
    """Conduct interactive requirement gathering to generate system prompt.
    
    Performs multi-turn conversation with user and LLM to:
    1. Gather system requirements
    2. Infer appropriate agent role
    3. Generate tailored system prompt
    
    Args:
        client: LLM client instance
        available_roles: List of available roles in the protocol
        context: Protocol/system context information
        max_tokens: Max tokens for LLM responses
        timeout: Timeout for LLM calls
        ui_callback: UI callback for user prompts
        logger_callback: Logging callback
    
    Returns:
        Tuple of (inferred_role, system_prompt) or (None, default_prompt) on failure
    """
    from .state_manager import extract_social_state
    from .llm_client import call_llm_with_timeout
    
    # Helper for logging
    def log_msg(msg, level='debug'):
        if logger_callback:
            logger_callback(msg, level)
    
    log_msg("\n=== Human-in-the-Loop Requirement Extraction ===")
    if context:
        log_msg(f"Context: {context}")
    if available_roles:
        roles_str = ', '.join(str(r) for r in available_roles)
        log_msg(f"Available roles: {roles_str}")
    
    # Collect initial requirements from user
    if ui_callback:
        ui_callback.start_requirements()
    user_requirements = _collect_user_input()
    
    if not user_requirements:
        return None, "You are a helpful agent. Be thorough and precise in your responses."
    
    # Perform initial LLM analysis of requirements
    analysis, conversation = await _analyze_requirements(
        client, user_requirements, available_roles, max_tokens, timeout, ui_callback, logger_callback
    )
    
    if ui_callback:
        ui_callback.show_analysis(analysis)
    
    # Optional refinement loop - allow user to refine requirements
    while True:
        if ui_callback:
            ui_callback.ask_refine_requirements()
        
        refine = input().strip().lower()
        if refine not in ["yes", "y"]:
            break
        
        if ui_callback:
            ui_callback.prompt_additional_requirements()
        
        additional = _collect_user_input()
        if not additional:
            continue
        
        # Add refinement to conversation and update analysis
        refine_prompt = f"Additional requirements: {additional}\n\nUpdate your analysis."
        conversation.append({"role": "user", "content": refine_prompt})
        
        refined = await _call_llm_for_analysis(
            client, refine_prompt, timeout, max_tokens, ui_callback, "refining requirements"
        )
        conversation.append({"role": "assistant", "content": refined})
        log_msg(f"\nRefined:\n{refined}\n")
        
        if ui_callback:
            ui_callback.show_analysis(refined)
    
    # Generate final system prompt from conversation history
    inferred_role, system_prompt = await _build_system_prompt_from_conversation(
        client, conversation, available_roles, max_tokens, timeout, ui_callback, logger_callback
    )
    
    return inferred_role, system_prompt
