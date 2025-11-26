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
    
    # Collect initial requirements
    if ui_callback:
        ui_callback.start_requirements()
    
    user_requirements = _collect_user_input()
    
    if not user_requirements:
        return None, "You are a helpful agent. Be thorough and precise in your responses."
    
    # First LLM analysis
    role_context = ""
    if available_roles:
        roles_str = ', '.join(str(r) for r in available_roles)
        role_context = f"\n\nAvailable roles: {roles_str}. Infer the best match."
    
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
    
    analysis = await _call_llm_for_analysis(
        client, analysis_prompt, timeout, max_tokens, ui_callback, "analyzing requirements"
    )
    log_msg(f"\n{'='*80}")
    log_msg(f"REQUIREMENT ANALYSIS RESPONSE")
    log_msg(f"{'='*80}")
    log_msg(analysis)
    log_msg(f"{'='*80}\n")
    
    if ui_callback:
        ui_callback.show_analysis(analysis)
    
    # Optional refinement loop
    conversation = [
        {"role": "user", "content": analysis_prompt},
        {"role": "assistant", "content": analysis}
    ]
    
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
        
        refine_prompt = f"Additional requirements: {additional}\n\nUpdate your analysis."
        conversation.append({"role": "user", "content": refine_prompt})
        
        refined = await _call_llm_for_analysis(
            client, refine_prompt, timeout, max_tokens, ui_callback, "refining requirements"
        )
        conversation.append({"role": "assistant", "content": refined})
        log_msg(f"\nRefined:\n{refined}\n")
        
        if ui_callback:
            ui_callback.show_analysis(refined)
    
    # Generate final system prompt
    roles_str = ', '.join(str(r) for r in available_roles) if available_roles else "any role"
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
    
    conversation.append({"role": "user", "content": final_prompt})
    full_conversation = "\n\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in conversation
    )
    
    log_msg(f"{'='*80}")
    log_msg(f"FINAL SYSTEM PROMPT GENERATION REQUEST")
    log_msg(f"{'='*80}")
    log_msg(full_conversation)
    log_msg(f"{'='*80}")
    
    final = await _call_llm_for_analysis(
        client, full_conversation, timeout, max_tokens, ui_callback, "generating system prompt"
    )
    
    log_msg(f"\n{'='*80}")
    log_msg(f"FINAL SYSTEM PROMPT GENERATION RESPONSE")
    log_msg(f"{'='*80}")
    log_msg(final)
    log_msg(f"{'='*80}\n")
    
    # Parse role and prompt
    inferred_role = _extract_role_from_response(final, available_roles)
    system_prompt = _extract_system_prompt_from_response(final)
    
    return inferred_role, system_prompt
