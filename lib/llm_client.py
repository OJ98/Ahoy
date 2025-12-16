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

    # Enhance system prompt with startup context if no message history exists
    enhanced_system_prompt = _SYSTEM_PROMPT_CACHE
    
    # DEBUG: Log message detection for troubleshooting
    log_msg(f"[choose_and_bind] Total messages found: {len(all_messages)}")
    for i, msg in enumerate(all_messages):
        msg_schema = msg.get("schema_name", "unknown")
        log_msg(f"  Message {i}: schema_name='{msg_schema}'")
    
    if not all_messages and enhanced_system_prompt:
        # Add startup guidance when no prior context exists
        startup_guidance = """

STARTUP CONTEXT:
This is the beginning of a new transaction. No prior message history exists.
Rather than decline to act, initialize the transaction with reasonable placeholder values:
- Use typical/generic but realistic identifiers (e.g., "ORDER_001", "Widget", "10 units")
- These values will evolve as the other parties respond and provide feedback
- Your role is to begin the workflow by proposing initial parameters
- Treating startup differently from operational refusal shows adaptive behavior"""
        enhanced_system_prompt = enhanced_system_prompt + startup_guidance
    
    # Add guidance about multi-option strategy if initial messages exist but exploration is possible
    if all_messages and enhanced_system_prompt:
        # Check if there are initial inquiry/request messages that might benefit from exploration
        has_inquiry_messages = any(
            msg.get("schema_name") and 
            any(keyword in msg.get("schema_name", "").lower() 
                for keyword in ["rfq", "inquiry", "request", "ask", "query"])
            for msg in all_messages
        )
        has_responses = any(
            msg.get("schema_name") and 
            any(keyword in msg.get("schema_name", "").lower() 
                for keyword in ["quote", "proposal", "offer", "response"])
            for msg in all_messages
        )
        has_final_decisions = any(
            msg.get("schema_name") and 
            any(keyword in msg.get("schema_name", "").lower() 
                for keyword in ["accept", "confirm"])  # Only accept/confirm are truly final
            for msg in all_messages
        )
        
        log_msg(f"[choose_and_bind] has_inquiry_messages={has_inquiry_messages}, has_responses={has_responses}, has_final_decisions={has_final_decisions}")
        
        # If we have responses, guide the LLM to evaluate and decide (accept/reject/complete)
        if has_responses and not has_final_decisions:
            decision_guidance = """

RESPONSE EVALUATION STRATEGY:
You have received response(s) to your inquiry. Now evaluate and make a decision:

DECISION TREE:
1. **Is the quote acceptable?** (within budget, correct delivery location, reasonable quality)
   - YES → Send an ACCEPT message with the delivery address and confirmation response
   - NO → Send a REJECT message with the reason (price too high, can't deliver, etc.)

2. **After acceptance, when you receive delivery confirmation:**
   - Send a COMPLETED message with satisfaction feedback

3. **Never abandon good deals** - If a quote meets your constraints, accept it.
   - Budget: Must be ≤ $20 total (including shipping/taxes)
   - Location: Must deliver to Raleigh, NC 27606
   - Product: Must be a functional pen

ACTION NOW: Choose one of the available options (accept/reject/completed) and provide all required parameters."""
            enhanced_system_prompt = enhanced_system_prompt + decision_guidance
        
        # Only suggest exploration if we have inquiries but NO responses yet
        elif has_inquiry_messages and not has_responses and not has_final_decisions:
            negotiation_guidance = """

MULTI-OPTION EXPLORATION STRATEGY:
You have sent inquiry message(s) but have not yet received responses. You may:

OPTION A: Wait for responses to your current inquiry (Recommended for single supplier)
OPTION B: Send NEW rfq messages with DIFFERENT ID values to explore other suppliers
✓ EXAMPLE: If you sent ID='TRANS_001', now send ID='TRANS_002' with different item specs
✓ PURPOSE: Get multiple quotes to compare options
✗ DO NOT: Reuse the same ID with different items (causes protocol errors)

Choose based on your strategy: single supplier or competitive bidding."""
            enhanced_system_prompt = enhanced_system_prompt + negotiation_guidance
        
        # Add completion guidance if we have accepted a transaction and received delivery
        has_accepted = any(
            msg.get("schema_name") and msg.get("schema_name", "").lower() == "accept"
            for msg in all_messages
        )
        has_delivered = any(
            msg.get("schema_name") and msg.get("schema_name", "").lower() == "deliver"
            for msg in all_messages
        )
        
        if has_accepted and has_delivered:
            completion_guidance = """

TRANSACTION COMPLETION DECISION:
You have:
1. Accepted a quote from the seller
2. Received delivery of the item from the shipper

COMPLETION ACTION:
If the delivery confirms the item meets your requirements (pen acquired at reasonable price):
- You can send a 'completed' message to indicate transaction success
- Use the same ID from the accepted quote for consistency
- Provide satisfaction feedback about the transaction
- This signals that the procurement goal is achieved

Only use the 'completed' message when you are genuinely satisfied with the outcome.
This represents the end of the transaction and your achievement of the procurement objective."""
            enhanced_system_prompt = enhanced_system_prompt + completion_guidance

    # Add critical guidance about avoiding duplicate messages
    if all_messages:
        duplicate_prevention = """

CRITICAL: AVOID DUPLICATE MESSAGES
DO NOT send the same message multiple times with different parameters (especially different 'resp' values).
- If you have already sent an accept/reject/completed message with a specific ID, do NOT send it again
- If asked for the same decision multiple times, choose null to decline
- Each message must have unique identity or reflect a genuinely different decision
- Protocol will reject duplicate messages with different parameter values

EXCEPTION: Only proceed with a decision if it genuinely reflects a NEW state change or NEW information."""
        enhanced_system_prompt = enhanced_system_prompt + duplicate_prevention

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

    # Validate parameter names
    for param_name in params.keys():
        if param_name not in chosen_partial.schema.parameters:
            log_msg(f"LLM returned unknown parameter '{param_name}'")
            return None

    # Bind parameters
    try:
        message_instance = chosen_partial.bind(**params)
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
