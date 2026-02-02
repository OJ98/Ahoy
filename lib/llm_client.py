#!/usr/bin/env python3
"""
Minimal LLM interaction client for the multi-agent system.
Provides: LLM completion, message selection with tool calling, and tool execution.
"""

import asyncio
import json
import os
import time
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING
import anthropic
import uuid as _uuid
from datetime import datetime as _datetime

if TYPE_CHECKING:
    from .llm_client import LLMClient


MODEL_ID = "claude-haiku-4-5-20251001"

# ============================================================================
# LLM CALL TRACKING
# ============================================================================

class LLMCallTracker:
    """Tracks LLM calls and enforces thresholds."""
    
    def __init__(self, max_calls: int = 20, max_duration_seconds: float = 180.0):
        """Initialize the tracker with thresholds."""
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
        """Check if any threshold has been exceeded."""
        if self.call_count >= self.max_calls:
            return True, f"LLM call limit reached ({self.call_count}/{self.max_calls})"
        
        elapsed = self.get_elapsed_seconds()
        if elapsed >= self.max_duration_seconds:
            minutes = elapsed / 60
            return True, f"Time limit reached ({minutes:.1f}/3.0 minutes)"
        
        return False, None
    
    def get_status(self) -> str:
        """Get current status: calls and elapsed time."""
        elapsed = self.get_elapsed_seconds()
        return f"{self.call_count} messages, {elapsed:.0f}s elapsed"


# Global tracker instance
_llm_call_tracker: Optional[LLMCallTracker] = None


def initialize_llm_tracker(max_calls: int = 20, max_duration_seconds: float = 180.0) -> LLMCallTracker:
    """Initialize the global LLM call tracker."""
    global _llm_call_tracker
    _llm_call_tracker = LLMCallTracker(max_calls, max_duration_seconds)
    return _llm_call_tracker


def get_llm_tracker() -> Optional[LLMCallTracker]:
    """Get the global LLM call tracker."""
    return _llm_call_tracker


def reset_llm_tracker() -> None:
    """Reset the global LLM call tracker."""
    global _llm_call_tracker
    _llm_call_tracker = None


# ============================================================================
# LLM CLIENT BASE AND IMPLEMENTATION
# ============================================================================

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


# ============================================================================
# HELPER FUNCTIONS
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
        max_tokens: Maximum response tokens
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

    Expected format: {"choice": <int|null>, "params": {"key": "value", ...}, "tool_requests": [...]}
    Also handles JSON wrapped in markdown code blocks.

    Args:
        text: JSON response text from LLM

    Returns:
        Dict with "choice", "params", and "tool_requests" keys, or None if invalid
    """
    if not text:
        return None
    
    import re
    
    # Try to extract JSON from markdown code blocks - find ALL blocks and use the one with "choice"
    code_blocks = list(re.finditer(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL))
    
    json_candidates = []
    if code_blocks:
        # Try each code block, preferring ones that contain "choice"
        for match in code_blocks:
            json_candidates.append(match.group(1).strip())
    else:
        # No markdown blocks found, use the whole text
        json_candidates = [text]
    
    # Try each candidate, starting with ones that look like they have "choice"
    candidates_with_choice = [c for c in json_candidates if '"choice"' in c or "'choice'" in c]
    candidates_without_choice = [c for c in json_candidates if c not in candidates_with_choice]
    
    for json_candidate in candidates_with_choice + candidates_without_choice:
        # Find valid JSON by finding opening brace and matching closing brace
        start_idx = json_candidate.find('{')
        if start_idx == -1:
            continue
        
        brace_count = 0
        bracket_count = 0
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
            
            if char == '"' and not in_string:
                in_string = True
                continue
            elif char == '"' and in_string:
                in_string = False
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
        
        if end_idx == -1:
            continue
        
        json_str = json_candidate[start_idx:end_idx]
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            continue
        
        # Ensure required fields
        if "choice" not in data:
            data["choice"] = None
        if "params" not in data:
            data["params"] = {}
        if "tool_requests" not in data:
            data["tool_requests"] = []
        
        return data
    
    # If we get here, no valid JSON was found
    return None


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
        agent_name: Name of agent making the call
        allow_tools: Whether to allow tool requests (default: True)

    Returns:
        Tuple of (choice_index, params_dict, raw_text, tool_requests) or None if parsing failed
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


async def choose_and_bind(
    adapter,
    enabled_store,
    event: dict,
    client: LLMClient,
    *,
    timeout: float,
    logger_callback=None,
    agent_name: str = "unknown",
    multi_protocol_states: Optional[Dict[str, Any]] = None
):
    """
    Prompt LLM to choose a message and bind its parameters.

    On first call: Calls build_system_prompt() and caches the result.
    On subsequent calls: Uses the cached system prompt.

    Args:
        adapter: Protocol adapter instance
        enabled_store: Enabled store with messages() method returning Partial objects
        event: Current event dict
        client: LLM client instance
        timeout: LLM call timeout in seconds
        logger_callback: Optional function for logging: logger_callback(message)
        agent_name: Name of the agent making the decision
        multi_protocol_states: Optional dict of {adapter_key: social_state} for multi-protocol scenarios

    Returns:
        Bound Message instance or None if no valid choice made
    """
    from .state_manager import extract_social_state
    from .utils import build_user_prompt, build_system_prompt

    global _system_prompt_cache
    
    # Track decision cycles for prompt optimization (e.g., show examples only on first decision)
    if not hasattr(choose_and_bind, '_decision_count'):
        choose_and_bind._decision_count = 0
    choose_and_bind._decision_count += 1

    def log_msg(msg):
        """Helper to log messages if callback provided."""
        if logger_callback:
            logger_callback(msg)

    log_msg("\n=== CHOOSE_AND_BIND INVOKED ===")

    # Extract adapter social state
    social_state = extract_social_state(adapter)
    adapter_name_obj = social_state.get('adapter_name', {})

    adapter_name = adapter_name_obj.get('name', 'unknown') if isinstance(adapter_name_obj, dict) else str(adapter_name_obj)
    
    log_msg(f"Adapter: {adapter_name}")

    # Initialize system prompt on first call
    if _system_prompt_cache is None:
        log_msg("First call detected - building and caching system prompt...")
        # For multi-protocol scenarios, include all protocol context
        if multi_protocol_states and len(multi_protocol_states) > 1:
            log_msg(f"Multi-protocol scenario with {len(multi_protocol_states)} active roles")
            _system_prompt_cache = build_system_prompt(list(multi_protocol_states.keys()))
        else:
            _system_prompt_cache = build_system_prompt(adapter_name)
        log_msg(f"System prompt cached (length: {len(_system_prompt_cache)})\n")
    else:
        log_msg("Using cached system prompt from previous call\n")

    # Build options from enabled messages
    options = []
    for idx, partial in enumerate(enabled_store.messages()):
        # Get missing params from schema definition
        missing_params = [
            param_name for param_name in partial.schema.parameters
            if partial.bindings.get(param_name) is None
        ]
        log_msg(f"Option {idx}: {partial.schema.qualified_name} - Missing: {missing_params}")
        options.append({
            "index": idx,
            "schema_name": partial.schema.qualified_name,
            "missing_params": missing_params,
            "partial": partial,
        })

    if not options:
        log_msg("No options available")
        return None

    # Extract all messages from social state
    all_messages = social_state.get("all_messages", [])
    if not all_messages:
        for system_info in social_state.get("systems", {}).values():
            all_messages.extend(system_info.get("all_messages", []))
    
    if not social_state.get("all_messages"):
        social_state["all_messages"] = all_messages
    
    # For multi-protocol scenarios, add context about other roles
    if multi_protocol_states and len(multi_protocol_states) > 1:
        social_state["multi_protocol_context"] = {
            key: state for key, state in multi_protocol_states.items()
            if key != adapter_name  # Don't duplicate current adapter info
        }

    # Build user prompt with decision count for optimization
    user_prompt = build_user_prompt(
        adapter_name,
        social_state,
        options,
        recent_event=event,
        decision_count=choose_and_bind._decision_count,
        examples=[
            {"choice": None, "params": {}},
            {"choice": 0, "params": {}},
        ]
    )

    log_msg(f"\n{'='*80}")
    log_msg(f"USER PROMPT FOR MESSAGE CHOICE (Decision #{choose_and_bind._decision_count})")
    log_msg(f"{'='*80}")
    log_msg(user_prompt)
    log_msg(f"{'='*80}")

    # Get LLM choice
    res = await choose_option_from_llm(
        client,
        user_prompt,
        timeout=timeout,
        system_prompt=_system_prompt_cache,
        agent_name=adapter_name,
        allow_tools=True
    )

    if not res:
        log_msg("LLM returned no usable result")
        return None

    choice_idx, params, raw_text, tool_requests = res

    # Log the raw LLM response
    log_msg(f"\n{'='*80}")
    log_msg(f"RAW LLM RESPONSE")
    log_msg(f"{'='*80}")
    log_msg(raw_text)
    log_msg(f"{'='*80}")

    # Handle tool requests if any
    if tool_requests:
        log_msg(f"\n{'='*80}")
        log_msg(f"EXECUTING TOOL REQUESTS")
        log_msg(f"{'='*80}")
        
        for tool_req in tool_requests:
            tool_name = tool_req.get("tool")
            tool_args = tool_req.get("args", {})
            log_msg(f"Executing tool: {tool_name} with args: {tool_args}")
            try:
                result = await execute_tool_call(tool_name, tool_args)
                result_obj = json.loads(result) if isinstance(result, str) else result
                log_msg(f"  Result: {result}")
                

            except Exception as e:
                log_msg(f"  Error: {str(e)}")
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
        log_msg("LLM declined to make a choice")
        return None

    if not (0 <= choice_idx < len(options)):
        log_msg(f"LLM chose invalid index: {choice_idx}")
        return None

    chosen_partial = options[choice_idx]["partial"]

    # Validate parameter names and filter out already-bound parameters
    filtered_params = {}
    for param_name, param_value in params.items():
        if param_name not in chosen_partial.schema.parameters:
            log_msg(f"LLM returned unknown parameter '{param_name}'")
            return None
        
        # Skip parameters that are already bound
        if param_name in chosen_partial.bindings and chosen_partial.bindings[param_name] is not None:
            log_msg(f"Skipping already-bound parameter '{param_name}'")
            continue
        
        filtered_params[param_name] = param_value

    # Auto-generate IDs for any unbound ID parameters
    from .utils import auto_generate_id_parameters
    auto_generated_ids = auto_generate_id_parameters(chosen_partial, logger_callback=log_msg)
    filtered_params.update(auto_generated_ids)

    # Bind parameters
    try:
        message_instance = chosen_partial.bind(**filtered_params)
    except Exception as exc:
        log_msg(f"Parameter binding failed: {exc}")
        return None

    return message_instance




# Global storage for system prompt (cached on first call to choose_and_bind)
_system_prompt_cache: Optional[str] = None

# Global storage for agent notes
_agent_notes_storage: Dict[str, Any] = {}


def save_state_to_memory(agent_name: str, key: str, value: str) -> Dict[str, str]:
    """
    Save important agent state/notes to memory for later recall.
    
    Args:
        agent_name: Name of the agent saving the note
        key: Key for the state entry (e.g., "current_transaction", "decision_rationale")
        value: Value to save
    
    Returns:
        Dict with status: {"status": "saved", "key": key, "value": value}
    """
    # Store in in-memory storage
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


def declare_protocol_and_role(protocol_name: str, role_name: str, reasoning: str = "") -> Dict[str, str]:
    """
    Declare which protocol and role an agent wants to participate in.
    
    Args:
        protocol_name: Name of the protocol (e.g., 'Purchase', 'Logistics')
        role_name: Name of the role (e.g., 'Buyer', 'Seller')
        reasoning: Explanation for the choice (optional)
    
    Returns:
        Dict with status and validation result
    """
    # Import here to avoid circular imports
    from .protocol_discovery import validate_protocol_and_role
    
    is_valid, error_msg = validate_protocol_and_role(protocol_name, role_name)
    
    if not is_valid:
        return {
            "status": "invalid",
            "error": error_msg
        }
    
    return {
        "status": "declared",
        "protocol": protocol_name,
        "role": role_name,
        "reasoning": reasoning
    }


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
    """Build list of optional tools for Claude tool use."""
    return [
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
        },
        {
            "name": "declare_protocol_and_role",
            "description": "Declare which protocol and role you want to participate in. Used during agent initialization to determine your participation.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "protocol_name": {
                        "type": "string",
                        "description": "Name of the protocol (e.g., 'Purchase', 'Logistics')"
                    },
                    "role_name": {
                        "type": "string",
                        "description": "Name of the role within the protocol (e.g., 'Buyer', 'Seller')"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Explain why you chose this protocol and role"
                    }
                },
                "required": ["protocol_name", "role_name"]
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
    if tool_name == "save_state_to_memory":
        result = save_state_to_memory(
            agent_name=tool_input.get("agent_name", "unknown"),
            key=tool_input.get("key", ""),
            value=tool_input.get("value", "")
        )
        return json.dumps({"tool": tool_name, "result": result})
    
    elif tool_name == "declare_protocol_and_role":
        result = declare_protocol_and_role(
            protocol_name=tool_input.get("protocol_name", ""),
            role_name=tool_input.get("role_name", ""),
            reasoning=tool_input.get("reasoning", "")
        )
        return json.dumps({"tool": tool_name, "result": result})
    
    else:
        return json.dumps({"tool": tool_name, "error": f"Unknown tool: {tool_name}"})


def reset_system_prompt_cache():
    """Reset the cached system prompt (useful for testing)."""
    global _system_prompt_cache
    _system_prompt_cache = None


def reset_optimization_caches():
    """Reset all optimization caches (system prompt and message history)."""
    from .utils import _message_history_cache, _protocol_guidance_cache
    global _system_prompt_cache
    
    _system_prompt_cache = None
    _message_history_cache.clear()
    _protocol_guidance_cache.clear()
    
    # Reset decision counter
    if hasattr(choose_and_bind, '_decision_count'):
        choose_and_bind._decision_count = 0


def reset_agent_notes_storage():
    """Reset the agent notes storage (useful for testing)."""
    global _agent_notes_storage
    _agent_notes_storage = {}
