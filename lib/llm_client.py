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
    max_tokens: int = 200,
    system_prompt: Optional[str] = None
) -> str:
    """
    Call LLM with a timeout constraint.

    Args:
        client: LLM client instance
        prompt: User prompt to send
        timeout: Maximum time in seconds before timing out
        max_tokens: Maximum response tokens (default: 200)
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

    Expected format: {"choice": <int|null>, "params": {"key": "value", ...}}
    
    Also handles JSON wrapped in markdown code blocks.

    Args:
        text: JSON response text from LLM

    Returns:
        Dict with "choice" (int or None) and "params" (dict), or None if invalid
    """
    if not text:
        return None
    
    # Try to extract JSON from markdown code blocks first
    import re
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    
    try:
        data = json.loads(text)
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

    return {"choice": choice, "params": params}


async def choose_option_from_llm(
    client: LLMClient,
    prompt: str,
    timeout: float = 30.0,
    system_prompt: Optional[str] = None
) -> Optional[Tuple[Optional[int], Dict[str, Any], str]]:
    """
    Prompt LLM to choose an option and return choice with parameters.

    Args:
        client: LLM client instance
        prompt: User prompt with options to choose from
        timeout: Timeout in seconds (default: 30)
        system_prompt: Optional system prompt for context

    Returns:
        Tuple of (choice_index, params_dict, raw_text) or None if parsing failed
    """
    try:
        text = await call_llm_with_timeout(
            client, prompt, timeout=timeout, system_prompt=system_prompt
        )
    except asyncio.TimeoutError:
        return None
    except Exception as e:
        return None

    parsed = parse_llm_json_reply(text)
    if not parsed:
        return None

    return parsed["choice"], parsed["params"], text


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
        has_final_decisions = any(
            msg.get("schema_name") and 
            any(keyword in msg.get("schema_name", "").lower() 
                for keyword in ["accept", "confirm"])  # Only accept/confirm are truly final
            for msg in all_messages
        )
        
        log_msg(f"[choose_and_bind] has_inquiry_messages={has_inquiry_messages}, has_final_decisions={has_final_decisions}")
        
        # Add multi-option guidance if there are inquiries and no FINAL acceptance yet
        # (rejections are OK - they're part of the negotiation process)
        if has_inquiry_messages and not has_final_decisions:
            negotiation_guidance = """

MULTI-OPTION EXPLORATION STRATEGY - CRITICAL:
You have already sent initial inquiry message(s). To continue negotiating:
✓ DO: Send NEW rfq messages with DIFFERENT ID values than previous ones
✓ EXAMPLE: If you sent ID='TRANS_001', now send ID='TRANS_002' or ID='OPTION_002'
✓ PURPOSE: This allows you to get multiple quotes and compare options
✗ DO NOT: Reuse the same ID with different item specifications (this causes protocol errors)
✗ DO NOT: Send only reject/accept - continue exploring other suppliers for better terms

Action: Generate a completely new transaction ID that has NOT been used before.
Vary the parameters (item description, ID) to explore different options from this or other suppliers.
This is key to achieving better procurement outcomes through comparison shopping."""
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

    # Get LLM choice
    res = await choose_option_from_llm(
        client,
        user_prompt,
        timeout=timeout,
        system_prompt=enhanced_system_prompt
    )

    if not res:
        log_msg("LLM returned no usable result")
        return None

    choice_idx, params, raw_text = res

    # Log the raw LLM response
    log_msg(f"\n{'='*80}")
    log_msg(f"RAW LLM RESPONSE")
    log_msg(f"{'='*80}")
    log_msg(raw_text)
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


def reset_system_prompt_cache():
    """Reset the cached system prompt (useful for testing)."""
    global _SYSTEM_PROMPT_CACHE
    _SYSTEM_PROMPT_CACHE = None
