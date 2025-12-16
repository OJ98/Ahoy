#!/usr/bin/env python3
"""
LLM interaction clients and utilities for the multi-agent system.
Handles all communication with language models.
"""

import asyncio
import json
import os
import time
from typing import Any, Dict, Optional, Tuple
import anthropic


MODEL_ID = "claude-haiku-4-5-20251001"

# ============================================================================
# LLM CALL TRACKING
# ============================================================================

class LLMCallTracker:
    """Tracks LLM calls and enforces thresholds."""
    
    def __init__(self, max_calls: int = 20, max_duration_seconds: float = 180.0):
        """
        Initialize the tracker with thresholds.
        
        Args:
            max_calls: Maximum number of LLM calls (default: 20)
            max_duration_seconds: Maximum duration in seconds (default: 180 = 3 minutes)
        """
        self.max_calls = max_calls
        self.max_duration_seconds = max_duration_seconds
        self.call_count = 0
        self.start_time = time.time()
    
    def increment_call(self) -> None:
        """Increment the call counter."""
        self.call_count += 1
    
    def get_elapsed_seconds(self) -> float:
        """Get elapsed time since tracker creation."""
        return time.time() - self.start_time
    
    def check_threshold_exceeded(self) -> Tuple[bool, Optional[str]]:
        """
        Check if any threshold has been exceeded.
        
        Returns:
            Tuple of (threshold_exceeded, reason_string)
            If threshold_exceeded is False, reason_string is None
        """
        if self.call_count >= self.max_calls:
            return True, f"LLM call limit reached ({self.call_count}/{self.max_calls})"
        
        elapsed = self.get_elapsed_seconds()
        if elapsed >= self.max_duration_seconds:
            minutes = elapsed / 60
            return True, f"Time limit reached ({minutes:.1f}/3.0 minutes)"
        
        return False, None
    
    def get_status(self) -> str:
        """
        Get current status as a minimal string showing message count and time.
        
        Returns:
            Status string with format: "{calls} messages, {time}s elapsed"
        """
        elapsed = self.get_elapsed_seconds()
        return f"{self.call_count} messages, {elapsed:.0f}s elapsed"


# Global tracker instance
_llm_call_tracker: Optional[LLMCallTracker] = None


def initialize_llm_tracker(max_calls: int = 20, max_duration_seconds: float = 180.0) -> LLMCallTracker:
    """
    Initialize the global LLM call tracker.
    
    Args:
        max_calls: Maximum number of LLM calls
        max_duration_seconds: Maximum duration in seconds
        
    Returns:
        The initialized LLMCallTracker instance
    """
    global _llm_call_tracker
    _llm_call_tracker = LLMCallTracker(max_calls, max_duration_seconds)
    return _llm_call_tracker


def get_llm_tracker() -> Optional[LLMCallTracker]:
    """Get the global LLM call tracker."""
    return _llm_call_tracker


def reset_llm_tracker() -> None:
    """Reset the global LLM call tracker (useful for testing)."""
    global _llm_call_tracker
    _llm_call_tracker = None


class LLMClient:
    """Base interface for LLM client implementations."""

    async def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 200,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Send a prompt to the LLM and get a response.

        Args:
            prompt: The user prompt to send
            max_tokens: Maximum tokens in the response (default: 200)
            system_prompt: Optional system context/instructions

        Returns:
            The LLM response text
        """
        raise NotImplementedError()


class AnthropicLLMClient(LLMClient):
    """Anthropic API client for Claude models."""

    def __init__(self, api_key: Optional[str] = None, model: str = MODEL_ID):
        """
        Initialize the Anthropic LLM client.

        Args:
            api_key: API key (defaults to ANTHROPIC_API_KEY environment variable)
            model: Model ID to use (defaults to claude-haiku-4-5-20251001)

        Raises:
            ValueError: If API key is not provided and not in environment
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)

    async def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 200,
        system_prompt: Optional[str] = None
    ) -> str:
        """Send prompt to Claude API asynchronously."""
        loop = asyncio.get_event_loop()

        # Build API call kwargs
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        # Run blocking API call in executor
        message = await loop.run_in_executor(
            None,
            lambda: self.client.messages.create(**kwargs)
        )
        response_text = message.content[0].text
        
        # Track the LLM call
        tracker = get_llm_tracker()
        if tracker:
            tracker.increment_call()
        
        return response_text


class MockLLMClient(LLMClient):
    """Mock LLM client returning fixed reply (useful for testing)."""

    def __init__(self, reply: str, delay: float = 0.0):
        """
        Initialize the mock LLM client.

        Args:
            reply: Fixed response to return for any prompt
            delay: Optional delay before responding (in seconds)
        """
        self.reply = reply
        self.delay = delay

    async def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 200,
        system_prompt: Optional[str] = None
    ) -> str:
        """Return fixed reply after optional delay."""
        if self.delay:
            await asyncio.sleep(self.delay)
        
        # Track the LLM call
        tracker = get_llm_tracker()
        if tracker:
            tracker.increment_call()
        
        return self.reply


# ============================================================================
# Helper Functions
# ============================================================================

async def call_llm_with_timeout(
    client: LLMClient,
    prompt: str,
    timeout: float,
    max_tokens: int = 1000,
    system_prompt: Optional[str] = None
) -> str:
    """
    Call LLM with a timeout constraint.

    Args:
        client: LLM client instance
        prompt: User prompt to send
        timeout: Maximum time in seconds before timing out
        max_tokens: Maximum response tokens (default: 1000 for tool requests with nested JSON)
        system_prompt: Optional system prompt

    Returns:
        LLM response text

    Raises:
        asyncio.TimeoutError: If call exceeds timeout
    """
    return await asyncio.wait_for(
        client.complete(prompt, max_tokens=max_tokens, system_prompt=system_prompt),
        timeout=timeout
    )


def parse_llm_json_reply(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse JSON response from LLM.

    Expected format: {"choice": <int|null>, "params": {"key": "value", ...}, "needs_tools": bool, "tool_requests": [...]}
    
    Also handles JSON wrapped in markdown code blocks.

    Args:
        text: JSON response text from LLM

    Returns:
        Dict with "choice" (int or None), "params" (dict), "needs_tools" (bool), and "tool_requests" (list), or None if invalid
    """
    if not text:
        return None
    
    # Try to extract JSON from markdown code blocks first
    import re
    
    # Find the start of JSON within markdown code blocks
    code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if code_block_match:
        # Get the content between the backticks
        json_candidate = code_block_match.group(1).strip()
    else:
        # No markdown block, use entire text
        json_candidate = text
    
    # Try to find valid JSON by finding opening brace and then matching braces
    # Start from the first '{' and count braces to find the matching '}'
    start_idx = json_candidate.find('{')
    if start_idx == -1:
        return None
    
    brace_count = 0
    bracket_count = 0  # Track square brackets too
    end_idx = -1
    in_string = False
    escape_next = False
    
    for i in range(start_idx, len(json_candidate)):
        char = json_candidate[i]
        
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                # Only stop when we've closed all braces AND all brackets
                if brace_count == 0 and bracket_count == 0:
                    end_idx = i + 1
                    break
            elif char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
    
    if end_idx == -1:
        return None
    
    json_text = json_candidate[start_idx:end_idx]
    
    try:
        data = json.loads(json_text)
    except (json.JSONDecodeError, ValueError):
        return None

    # Validate structure
    if not isinstance(data, dict):
        return None

    choice = data.get("choice")
    if choice is not None and not isinstance(choice, int):
        return None

    params = data.get("params", {})
    if not isinstance(params, dict):
        return None

    needs_tools = data.get("needs_tools", False)
    if not isinstance(needs_tools, bool):
        return None

    tool_requests = data.get("tool_requests", [])
    if not isinstance(tool_requests, list):
        return None

    return {
        "choice": choice,
        "params": params,
        "needs_tools": needs_tools,
        "tool_requests": tool_requests
    }



async def choose_option_from_llm(
    client: LLMClient,
    prompt: str,
    timeout: float = 30.0,
    system_prompt: Optional[str] = None,
    agent_name: str = "unknown",
    allow_tools: bool = True
) -> Optional[Tuple[Optional[int], Dict[str, Any], str, list]]:
    """
    Prompt LLM to choose an option and return choice with parameters.
    
    Supports LLM-requested tool calls via JSON response.

    Args:
        client: LLM client instance
        prompt: User prompt with options to choose from
        timeout: Timeout in seconds (default: 30)
        system_prompt: Optional system prompt for context
        agent_name: Name of agent making the call (for tool context)
        allow_tools: Whether to allow tool requests (default: True)

    Returns:
        Tuple of (choice_index, params_dict, raw_text, tool_requests) or None if parsing failed
        where tool_requests is a list of tool call requests from LLM (may be empty)
    """
    try:
        text = await call_llm_with_timeout(
            client, prompt, timeout=timeout, system_prompt=system_prompt
        )
    except asyncio.TimeoutError:
        import logging
        logging.getLogger().debug(f"LLM timeout for {agent_name}")
        return None
    except Exception as e:
        import logging
        logging.getLogger().debug(f"LLM error for {agent_name}: {str(e)}")
        return None

    if not text:
        import logging
        logging.getLogger().debug(f"LLM returned empty response for {agent_name}")
        return None

    parsed = parse_llm_json_reply(text)
    if not parsed:
        import logging
        logging.getLogger().debug(f"Failed to parse LLM response for {agent_name}")
        logging.getLogger().debug(f"RAW UNPARSEABLE RESPONSE:\n{text[:500]}")
        return None

    return parsed["choice"], parsed["params"], text, parsed.get("tool_requests", [])


# Global cache for system prompt across multiple LLM calls
_SYSTEM_PROMPT_CACHE = None


# ============================================================================
# SYSTEM PROMPT CONSTRUCTION: Build enhanced prompts based on transaction state
# ============================================================================

def construct_system_prompt(
    base_prompt: str,
    all_messages: list,
    log_callback=None
) -> str:
    """
    Construct an enhanced system prompt with contextual guidance.
    
    Takes the base system prompt (which contains protocol-specific constraints
    and decisions) and adds generic process guidance based on the current
    state of the transaction (messages seen, decisions made, etc.).
    
    This function is protocol-agnostic - it detects generic patterns like
    "inquiries sent", "responses received", "decisions made" without assuming
    any specific message types, constraints, or workflows.
    
    Args:
        base_prompt: The base system prompt (from user requirements gathering)
        all_messages: List of all messages seen so far in the transaction
        log_callback: Optional function for logging
    
    Returns:
        Enhanced system prompt with generic process guidance appended
    """
    def log_msg(msg):
        if log_callback:
            log_callback(msg)
    
    # BSPL Protocol Explanation
    bspl_explanation = """
    You are participating in BSPL (Blindingly Simple Protocol Language) protocol enactments. 
    BSPL defines multi-agent protocols where:
    - Roles are named agents (e.g., Merchant, Buyer)
    - Messages are directed communication between roles with parameters marked as `out` (sender provides) or `in` (requires prior binding from other messages)
    - Parameters marked `key` identify protocol instances
    - You play one role and must track received messages to determine which messages you can legally send next
    - A message can only be sent when all its `in` parameters are bound by prior messages
    - When multiple messages are enabled, choose based on domain reasoning and the protocol's intended flow"""


    # Prepend BSPL explanation to the base prompt
    enhanced_prompt = bspl_explanation + "\n\n" + base_prompt
    
    # STARTUP GUIDANCE: If no prior messages, guide initial action
    if not all_messages and enhanced_prompt:
        startup_guidance = """

STARTUP CONTEXT:
This is the beginning of a new interaction. No prior message history exists.
Your role is to initialize the workflow by selecting an appropriate initial message
and providing necessary parameters. Use the constraints and decision criteria from
your system prompt to guide your choice."""
        enhanced_prompt = enhanced_prompt + startup_guidance
        return enhanced_prompt
    
    # Skip context-specific guidance if no messages
    if not all_messages:
        return enhanced_prompt
    
    # GENERIC STATE ANALYSIS: Detect workflow phase based on message patterns
    # Count different message categories without assuming protocol-specific types
    all_schema_names = [msg.get("schema_name", "").lower() for msg in all_messages]
    total_messages = len(all_messages)
    
    log_msg(f"[construct_system_prompt] Message history: {total_messages} messages total")
    log_msg(f"  Message types seen: {set(all_schema_names)}")
    
    # Add workflow phase reminder for multi-turn interactions
    if total_messages > 0:
        workflow_reminder = f"""

WORKFLOW CONTEXT:
You have {total_messages} message(s) in the conversation history. Review them carefully
and use your system prompt constraints and decision criteria to determine your next action.
Each message you send should represent a deliberate decision based on the current state."""
        enhanced_prompt = enhanced_prompt + workflow_reminder
    
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
    
    # CRITICAL: Prevent duplicate messages (applies to all protocols)
    duplicate_prevention = """

CRITICAL: AVOID DUPLICATE MESSAGES AND PARAMETERS
- Each message ID must be sent at most once with the exact same parameters
- Do NOT reuse the same ID with different descriptions, values, or wording
- Do NOT send similar messages with slight variations (capitalization, wording, etc.)
- Do NOT create near-duplicates with the same ID but different parameter values

If you need to retry a message:
- Use the EXACT SAME parameter values as before
- Do not generate new descriptions or parameter values

If the protocol rejects a message with a specific ID:
- Either accept the rejection and move forward with a different message type
- Or create a completely NEW message with a DIFFERENT ID
- Never retry the same ID with modified parameters

Protocol enforcement: Messages with the same schema and ID but different parameters will be rejected."""
    enhanced_prompt = enhanced_prompt + duplicate_prevention
    
    # CRITICAL: Guide rejection decisions to prevent premature rejections
    rejection_guidance = """

CRITICAL: REJECTION AND COMPARISON STRATEGY (Protocol-Agnostic)
When you receive multiple response options (quotes, offers, proposals, or any message variants):
- DO NOT immediately reject/dismiss after seeing just one option
- WAIT to see multiple options before making rejection decisions
- COMPARE all available alternatives before deciding to reject any
- Only reject if: (1) multiple options have arrived AND (2) this option is clearly inferior
- If unsure, ASK FOR MORE INFORMATION rather than rejecting

Rejection consequences (vary by protocol):
- Once you reject/dismiss an option with a specific ID, you may not be able to revert that decision
- Rejecting too early removes your alternatives when better options arrive later
- Protocol state may prevent you from accepting a previously rejected option

Strategy:
1. On first option received: Do NOT reject immediately - wait for competing options
2. When multiple options arrive: Compare them all before deciding
3. Select the best option or request additional information
4. Only reject if the option is clearly unacceptable even with alternatives available

This approach maximizes your choices and prevents losing good options due to premature rejection."""
    enhanced_prompt = enhanced_prompt + rejection_guidance
    
    # TOOL USAGE: Instruct agent to use save_state_to_memory tool for audit trail
    tool_usage_guidance = """

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
    enhanced_prompt = enhanced_prompt + tool_usage_guidance
    
    return enhanced_prompt



async def choose_and_bind(
    adapter,
    enabled_store,
    event: dict,
    client: LLMClient,
    *,
    timeout: float,
    logger_callback=None,
    requirement_callback=None
):
    """
    Prompt LLM to choose a message and bind its parameters.

    Workflow:
    1. On first call: Execute requirement_callback to generate system prompt
    2. Collect enabled Partial objects from enabled_store.messages()
    3. Build user prompt with enabled messages and social state
    4. Use cached system prompt for all LLM calls
    5. Call LLM to pick option index and provide parameters
    6. Validate and bind parameters to create Message instance

    Args:
        adapter: Protocol adapter instance
        enabled_store: Enabled store with messages() method returning Partial objects
        event: Current event dict
        client: LLM client instance
        timeout: LLM call timeout in seconds
        logger_callback: Optional function for logging: logger_callback(message, level='debug')
        requirement_callback: Optional async callable that gathers requirements:
                             async (roles) -> (role, system_prompt)

    Returns:
        Bound Message instance or None if no valid choice made
    """
    from .state_manager import extract_social_state
    from .utils import build_user_prompt

    global _SYSTEM_PROMPT_CACHE

    def log_msg(msg, level='debug'):
        """Helper to log messages if callback provided."""
        if logger_callback:
            logger_callback(msg)

    log_msg("\n=== CHOOSE_AND_BIND INVOKED ===")

    # Extract adapter social state
    social_state = extract_social_state(adapter)
    adapter_name_obj = social_state.get('adapter_name', {})
    adapter_name = adapter_name_obj.get('name', 'unknown') if isinstance(adapter_name_obj, dict) else str(adapter_name_obj)
    adapter_roles = social_state.get('roles', [])

    log_msg(f"\n=== Extracted Social State ===")
    log_msg(f"Adapter: {adapter_name}")
    log_msg(f"Roles: {adapter_roles}\n")

    # Initialize system prompt on first call
    if _SYSTEM_PROMPT_CACHE is None:
        if requirement_callback:
            log_msg("\n=== First-time initialization: Gathering system requirements ===")
            inferred_role, system_prompt = await requirement_callback(adapter_roles)
            _SYSTEM_PROMPT_CACHE = system_prompt
            log_msg(f"Inferred role: {inferred_role}\n")
            log_msg("System prompt cached for future LLM calls.\n")
        else:
            log_msg("Warning: No requirement callback provided for system prompt generation")
            return None

    # Build options from enabled messages
    options = []
    for idx, partial in enumerate(enabled_store.messages()):
        # Get missing params from schema definition, not just what's in bindings
        missing_params = [
            param_name for param_name in partial.schema.parameters
            if partial.bindings.get(param_name) is None
        ]
        log_msg(f"Option {idx}: {partial.schema.qualified_name} - Schema params: {partial.schema.parameters}, Missing: {missing_params}, Bindings: {partial.bindings}")
        options.append({
            "index": idx,
            "schema_name": partial.schema.qualified_name,
            "missing_params": missing_params,
            "partial": partial,
            "sender": partial.schema.sender.name,
            "recipients": [r.name for r in partial.schema.recipients],
        })

    if not options:
        return None

    # Extract all messages from social state (which may have messages nested in systems)
    # Do this BEFORE building user prompt so the history is available
    all_messages = social_state.get("all_messages", [])
    if not all_messages:
        # Try to extract from systems if at top level doesn't exist
        for system_info in social_state.get("systems", {}).values():
            all_messages.extend(system_info.get("all_messages", []))
    
    # Ensure social_state has all_messages at top level for build_user_prompt to use
    if not social_state.get("all_messages"):
        social_state["all_messages"] = all_messages

    # Build user prompt (now has access to all_messages)
    user_prompt = build_user_prompt(
        adapter_name,
        social_state,
        options,
        recent_event=event,
        examples=[
            {"choice": None, "params": {}},
            {"choice": 0, "params": {}},
        ]
    )

    # Enhance system prompt with contextual guidance based on transaction state
    enhanced_system_prompt = construct_system_prompt(
        _SYSTEM_PROMPT_CACHE,
        all_messages,
        log_callback=log_msg
    )
    
# Log cached system prompt and user prompt
    log_msg(f"\n{'='*80}")
    log_msg(f"SYSTEM PROMPT (CACHED)")
    log_msg(f"{'='*80}")
    log_msg(enhanced_system_prompt if enhanced_system_prompt else "[None - not initialized]")
    log_msg(f"{'='*80}")

    log_msg(f"\n{'='*80}")
    log_msg(f"USER PROMPT FOR MESSAGE CHOICE")
    log_msg(f"{'='*80}")
    log_msg(user_prompt)
    log_msg(f"{'='*80}")

    # Get LLM choice (may include tool requests)
    res = await choose_option_from_llm(
        client,
        user_prompt,
        timeout=timeout,
        system_prompt=enhanced_system_prompt,
        agent_name=adapter_name,
        allow_tools=True
    )

    if not res:
        log_msg("LLM returned no usable result - attempting to retrieve raw response for debugging...")
        # Try to get the raw response from the last LLM call for debugging
        try:
            # Call LLM one more time just to see what it returns (for debugging)
            test_text = await call_llm_with_timeout(
                client, user_prompt, timeout=10, system_prompt=enhanced_system_prompt
            )
            if test_text:
                log_msg(f"\n{'='*80}")
                log_msg(f"RAW LLM RESPONSE (unparseable)")
                log_msg(f"{'='*80}")
                log_msg(test_text[:1000])  # First 1000 chars
                log_msg(f"{'='*80}")
        except:
            pass
        return None

    choice_idx, params, raw_text, tool_requests = res

    # Log the raw LLM response
    log_msg(f"\n{'='*80}")
    log_msg(f"RAW LLM RESPONSE")
    log_msg(f"{'='*80}")
    log_msg(raw_text)
    log_msg(f"{'='*80}")

    # Handle tool requests if any
    tool_results = []
    if tool_requests:
        log_msg(f"\n{'='*80}")
        log_msg(f"EXECUTING TOOL REQUESTS")
        log_msg(f"{'='*80}")
        
        # IMPORTANT: Store original params before tool execution
        # These are the params the LLM committed to, and we'll use them even after tools run
        original_params = params.copy()
        
        for tool_req in tool_requests:
            tool_name = tool_req.get("tool")
            tool_args = tool_req.get("args", {})
            log_msg(f"Executing tool: {tool_name} with args: {tool_args}")
            try:
                result = await execute_tool_call(tool_name, tool_args)
                result_obj = json.loads(result) if isinstance(result, str) else result
                tool_results.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result_obj,
                    "status": "success"
                })
                log_msg(f"  Result: {result}")
                
                # IMPORTANT: If a tool generates a value (like generate_unique_id), 
                # update the corresponding param if it was a placeholder
                if tool_name == "generate_unique_id" and result_obj:
                    actual_result = result_obj.get("result") if isinstance(result_obj, dict) else result_obj
                    if "ID" in params and (params["ID"] is None or "TBD" in str(params["ID"]) or "PENDING" in str(params["ID"])):
                        params["ID"] = actual_result
                        log_msg(f"  Updated param ID to: {actual_result}")
                        
            except Exception as e:
                log_msg(f"  Error: {str(e)}")
                tool_results.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "error": str(e),
                    "status": "error"
                })
        log_msg(f"{'='*80}")
        
        # Log tool results summary
        log_msg(f"\n{'='*80}")
        log_msg(f"TOOL EXECUTION SUMMARY")
        log_msg(f"{'='*80}")
        log_msg(json.dumps(tool_results, indent=2))
        log_msg(f"{'='*80}")

    # Log the parsed LLM response
    log_msg(f"{'='*80}")
    log_msg(f"PARSED LLM RESPONSE")
    log_msg(f"{'='*80}")
    response_obj = {"choice": choice_idx, "params": params}
    log_msg(json.dumps(response_obj, indent=2))
    log_msg(f"{'='*80}")

    # Validate choice
    if choice_idx is None:
        log_msg("LLM declined to make a choice. No default selection.")
        return None

    if not (0 <= choice_idx < len(options)):
        log_msg(f"LLM chose invalid index: {choice_idx}")
        return None

    chosen_partial = options[choice_idx]["partial"]

    # VALIDATION: Log what the LLM chose vs what's bound to ensure successful enactment
    log_msg(f"\n{'='*80}")
    log_msg(f"DECISION VALIDATION - Ensuring Enactment Success")
    log_msg(f"{'='*80}")
    log_msg(f"LLM chose: Option {choice_idx} ({options[choice_idx].get('schema_name')})")
    log_msg(f"Message type: {chosen_partial.schema.qualified_name}")
    
    # Log all bound parameters (protocol-level bindings)
    bound_params = {k: v for k, v in chosen_partial.bindings.items() if v is not None}
    if bound_params:
        log_msg(f"Protocol-bound parameters (non-overridable):")
        for key, value in bound_params.items():
            log_msg(f"  {key}: {value}")
    
    # Log LLM-provided parameters
    if params:
        log_msg(f"LLM-provided parameters (to fill missing values):")
        for key, value in params.items():
            log_msg(f"  {key}: {value}")
    
    # Log decision details for human debugging (but don't automatically save)
    log_msg(f"\n{'='*80}")
    log_msg(f"DECISION: Option {choice_idx} ({options[choice_idx].get('schema_name')})")
    log_msg(f"Message type: {chosen_partial.schema.qualified_name}")
    
    if bound_params:
        log_msg(f"This message will use bound parameters:")
        for param_name, param_value in bound_params.items():
            log_msg(f"  {param_name}: {param_value}")
    
    log_msg(f"⚠️ REMINDER: Use save_state_to_memory tool to record your decision intent")
    log_msg(f"{'='*80}\n")

    # Validate parameter names and filter out already-bound parameters
    filtered_params = {}
    for param_name, param_value in params.items():
        if param_name not in chosen_partial.schema.parameters:
            log_msg(f"LLM returned unknown parameter '{param_name}'")
            return None
        
        # Skip parameters that are already bound (in parameters)
        if param_name in chosen_partial.bindings and chosen_partial.bindings[param_name] is not None:
            log_msg(f"Skipping already-bound parameter '{param_name}' (will use bound value: {chosen_partial.bindings[param_name]})")
            continue
        
        filtered_params[param_name] = param_value

    # Bind parameters (now only with unbound params)
    try:
        message_instance = chosen_partial.bind(**filtered_params)
    except Exception as exc:
        log_msg(f"Parameter binding failed: {exc}")
        return None

    return message_instance


# ============================================================================
# OPTIONAL TOOL CALLING: Note taking and UID generation
# ============================================================================

import uuid as _uuid
from datetime import datetime as _datetime

# Global storage for agent notes (can be used by tools)
_agent_notes_storage: Dict[str, Any] = {}


def generate_unique_id(prefix: str = "TXN", purpose: str = "") -> str:
    """
    Generate a unique transaction ID with optional prefix and timestamp.
    
    Args:
        prefix: Prefix for the ID (default: "TXN")
        purpose: Purpose description (optional, for logging)
    
    Returns:
        Unique ID string in format: {prefix}_{hex_uuid}_{timestamp}
    """
    unique_hex = _uuid.uuid4().hex[:8].upper()
    timestamp = _datetime.now().strftime("%H%M")
    return f"{prefix}_{unique_hex}_{timestamp}"


def save_state_to_memory(agent_name: str, key: str, value: str) -> Dict[str, str]:
    """
    Save important agent state/notes to memory for later recall.
    
    Also records the saved content to the agent_notes.json file.
    
    Args:
        agent_name: Name of the agent saving the note
        key: Key for the state entry (e.g., "current_transaction", "decision_rationale")
        value: Value to save
    
    Returns:
        Dict with status: {"status": "saved", "key": key, "value": value}
    """
    # Store in in-memory storage (for tool access during this run)
    if agent_name not in _agent_notes_storage:
        _agent_notes_storage[agent_name] = {}
    
    _agent_notes_storage[agent_name][key] = value
    
    # Also record to agent_notes.json (persistent notes file)
    try:
        from .agent_notes import get_agent_notes
        notes = get_agent_notes(agent_name)
        notes.save(key, value)
    except Exception as e:
        # Don't fail the tool if notes recording fails
        print(f"Warning: Could not save to agent_notes for {agent_name}: {e}")
    
    return {"status": "saved", "key": key, "value": value}


def get_agent_memory(agent_name: str, key: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve agent notes/state from memory.
    
    Args:
        agent_name: Name of the agent
        key: Optional specific key to retrieve. If None, returns all stored state.
    
    Returns:
        Dict with the requested state data
    """
    if agent_name not in _agent_notes_storage:
        return {"status": "no_data", "agent": agent_name}
    
    if key is None:
        return {"status": "retrieved", "agent": agent_name, "data": _agent_notes_storage[agent_name]}
    
    if key in _agent_notes_storage[agent_name]:
        return {"status": "retrieved", "key": key, "value": _agent_notes_storage[agent_name][key]}
    
    return {"status": "not_found", "agent": agent_name, "key": key}


def build_optional_tools() -> list:
    """
    Build list of optional tools for Claude tool use.
    
    Returns:
        List of tool definitions for Anthropic API
    """
    return [
        {
            "name": "generate_unique_id",
            "description": "Generate a unique transaction ID for a new message or decision point",
            "input_schema": {
                "type": "object",
                "properties": {
                    "prefix": {
                        "type": "string",
                        "description": "Prefix for the ID (default: 'TXN'). Examples: 'TXN', 'RFQ', 'ORDER'",
                        "default": "TXN"
                    },
                    "purpose": {
                        "type": "string",
                        "description": "Purpose of this ID for documentation (optional)",
                        "default": ""
                    }
                },
                "required": []
            }
        },
        {
            "name": "save_state_to_memory",
            "description": "Save important agent state or decision notes to memory for recall in future steps",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Name of this agent"
                    },
                    "key": {
                        "type": "string",
                        "description": "Key for the state entry (e.g., 'current_transaction', 'decision_rationale')"
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to save"
                    }
                },
                "required": ["agent_name", "key", "value"]
            }
        }
    ]


async def execute_tool_call(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """
    Execute a tool call and return the result as a string.
    
    Args:
        tool_name: Name of the tool to execute
        tool_input: Input parameters for the tool
    
    Returns:
        JSON string with the tool result
    """
    if tool_name == "generate_unique_id":
        result = generate_unique_id(
            prefix=tool_input.get("prefix", "TXN"),
            purpose=tool_input.get("purpose", "")
        )
        return json.dumps({"tool": tool_name, "result": result})
    
    elif tool_name == "save_state_to_memory":
        result = save_state_to_memory(
            agent_name=tool_input.get("agent_name", "unknown"),
            key=tool_input.get("key", ""),
            value=tool_input.get("value", "")
        )
        return json.dumps({"tool": tool_name, "result": result})
    
    else:
        return json.dumps({"tool": tool_name, "error": f"Unknown tool: {tool_name}"})


async def call_llm_with_optional_tools(
    client: LLMClient,
    prompt: str,
    timeout: float,
    agent_name: str = "unknown",
    max_tokens: int = 500,
    system_prompt: Optional[str] = None
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Call LLM with optional tool use support.
    
    Args:
        client: LLM client instance
        prompt: User prompt
        timeout: Timeout in seconds
        agent_name: Name of agent making the call (for tool execution context)
        max_tokens: Maximum response tokens
        system_prompt: Optional system prompt
    
    Returns:
        Tuple of (response_text, tool_calls_dict)
        where tool_calls_dict is None if no tools used, or a dict with tool results
    """
    # For now, if it's an AnthropicLLMClient, support tool use
    # Otherwise, fall back to regular completion
    if not isinstance(client, AnthropicLLMClient):
        text = await call_llm_with_timeout(client, prompt, timeout, max_tokens, system_prompt)
        return text, None
    
    loop = asyncio.get_event_loop()
    
    # Build API call with tool definitions
    tools = build_optional_tools()
    kwargs = {
        "model": client.model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "tools": tools,
        "tool_choice": {"type": "auto"},  # Let Claude decide whether to use tools
    }
    if system_prompt:
        kwargs["system"] = system_prompt
    
    # Make the API call
    try:
        message = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: client.client.messages.create(**kwargs)
            ),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise
    
    # Track the LLM call
    tracker = get_llm_tracker()
    if tracker:
        tracker.increment_call()
    
    # Extract response and process tool use
    response_text = ""
    tool_results = {}
    tool_calls_made = []
    
    # Process content blocks
    for block in message.content:
        if hasattr(block, 'text') and block.text:
            response_text += block.text
        elif block.type == "tool_use":
            tool_calls_made.append({
                "id": block.id,
                "name": block.name,
                "input": block.input
            })
    
    # Execute any tool calls and collect results
    if tool_calls_made:
        for tool_call in tool_calls_made:
            result = await execute_tool_call(tool_call["name"], tool_call["input"])
            tool_results[tool_call["name"]] = json.loads(result)
    
    return response_text, tool_results if tool_results else None


def reset_system_prompt_cache():
    """Reset the cached system prompt (useful for testing)."""
    global _SYSTEM_PROMPT_CACHE
    _SYSTEM_PROMPT_CACHE = None


def reset_agent_notes_storage():
    """Reset the agent notes storage (useful for testing)."""
    global _agent_notes_storage
    _agent_notes_storage = {}
