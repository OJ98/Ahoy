#!/usr/bin/env python3
import asyncio
import json
import os
import sys
from typing import Any, Dict, Optional, Tuple
from io import TextIOWrapper
import anthropic

# Ensure UTF-8 encoding for stdout on Windows
if sys.platform == 'win32':
    sys.stdout = TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

MODEL_ID = "claude-haiku-4-5-20251001"

# Global system prompt cache for multi-agent interactions
_SYSTEM_PROMPT_CACHE = None


# Minimal async LLM client interface
class LLMClient:
    async def complete(self, prompt: str, *, max_tokens: int = 200, system_prompt: Optional[str] = None) -> str:
        # Stub for LLM API integration
        raise NotImplementedError()

class AnthropicLLMClient(LLMClient):
    """Anthropic API client for Claude models."""
    def __init__(self, api_key: Optional[str] = None, model: str = MODEL_ID):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)

    async def complete(self, prompt: str, *, max_tokens: int = 200, system_prompt: Optional[str] = None) -> str:
        # Run the API call in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        # Build messages with optional system prompt
        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages
        }
        
        # Add system prompt if provided
        if system_prompt:
            kwargs["system"] = system_prompt
        
        message = await loop.run_in_executor(
            None,
            lambda: self.client.messages.create(**kwargs)
        )
        return message.content[0].text

class MockLLMClient(LLMClient):
    """Deterministic mock returning `reply` after optional delay (useful for tests)."""
    def __init__(self, reply: str, delay: float = 0.0):
        self.reply = reply
        self.delay = delay

    async def complete(self, prompt: str, *, max_tokens: int = 200, system_prompt: Optional[str] = None) -> str:
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.reply


# Helper Functions
async def call_llm_with_timeout(client: LLMClient, prompt: str, timeout: float, max_tokens: int = 200, system_prompt: Optional[str] = None) -> str:
    return await asyncio.wait_for(client.complete(prompt, max_tokens=max_tokens, system_prompt=system_prompt), timeout=timeout)

# Print enabled_store in human-readable format
def print_enabled_store(enabled_store):
    """
    Print the contents of enabled_store in a human-readable form.
    
    Args:
        enabled_store: An enabled store object with a messages() method
    """
    messages = list(enabled_store.messages())
    
    if not messages:
        print("enabled_store is empty (no messages)")
        return
    
    print(f"\n{'='*80}")
    print(f"ENABLED STORE CONTENTS ({len(messages)} message(s))")
    print(f"{'='*80}\n")
    
    for idx, partial in enumerate(messages):
        print(f"[{idx}] Message:")
        print(f"    Schema Name: {partial.schema.qualified_name}")
        print(f"    Sender: {partial.schema.sender.name}")
        print(f"    Recipients: {[r.name for r in partial.schema.recipients]}")
        print(f"    Parameters:")
        
        if hasattr(partial, 'bindings') and partial.bindings:
            for param_name, param_value in partial.bindings.items():
                status = "[BOUND]" if param_value is not None else "[MISSING]"
                print(f"        {param_name}: {param_value} {status}")
        else:
            print(f"        (no bindings)")
        
        print()
    
    print(f"{'='*80}\n")

# Print the constructed user prompt for debugging
def print_user_prompt(prompt: str, title: str = "USER PROMPT"):
    """
    Print the constructed user prompt in a readable format.
    
    Args:
        prompt: The user prompt string to display
        title: Optional title for the output section
    """
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}\n")
    print(prompt)
    print(f"\n{'='*80}\n")

# Print the LLM response for debugging
def print_llm_response(response: Any, title: str = "LLM RESPONSE"):
    """
    Print the LLM response in a readable format.
    Handles both raw string responses and parsed result tuples.
    If the response is JSON string, it will be pretty-printed.
    
    Args:
        response: The LLM response (can be string or tuple of (choice, params))
        title: Optional title for the output section
    """
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}\n")
    
    # Handle tuple response (choice_idx, params)
    if isinstance(response, tuple):
        choice_idx, params = response
        output_dict = {"choice": choice_idx, "params": params}
        print(json.dumps(output_dict, indent=2))
    # Handle string response
    elif isinstance(response, str):
        # Try to parse and pretty-print as JSON
        try:
            parsed_json = json.loads(response)
            print(json.dumps(parsed_json, indent=2))
        except (json.JSONDecodeError, ValueError):
            # If not JSON, print as-is
            print(response)
    else:
        # Fallback for other types
        print(str(response))
    
    print(f"\n{'='*80}\n")

# Parse LLM JSON reply
def parse_llm_json_reply(text: str) -> Optional[Dict[str, Any]]:
    """
    Expect JSON: {"choice": <int|null>, "params": {"p":"v", ...}}
    Returns dict or None on parse/validation failure.
    """
    try:
        data = json.loads(text)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    choice = data.get("choice", None)
    params = data.get("params", {}) or {}
    if choice is not None and not isinstance(choice, int):
        return None
    if not isinstance(params, dict):
        return None
    return {"choice": choice, "params": params}

class RoleEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Role objects"""
    def default(self, obj):
        if hasattr(obj, 'name'):
            return obj.name
        return super().default(obj)

# Convert adapter protocol info to JSON
def protocol_to_json(adapter):
    """
    Convert adapter's protocol information (roles and name) to JSON.
    
    Args:
        adapter: An Adapter instance
        
    Returns:
        str: JSON string containing adapter name and roles
    """
    data = {
        "name": adapter.name,
        "roles": sorted(list(adapter.roles))
    }
    return json.dumps(data, cls=RoleEncoder)

# Human-in-the-loop requirement extraction
async def gather_requirements_from_user(client: LLMClient, available_roles: list = None, context: str = "", *, max_tokens: int = 1000, timeout: float = 30.0) -> Tuple[Optional[str], str]:
    """
    Conduct a human-in-the-loop conversation via the LLM to determine system requirements and infer agent role.
    
    This function:
    1. Prompts the user through stdin for their requirements
    2. Sends user input to the LLM to infer the appropriate agent role
    3. Iteratively refines requirements through LLM-mediated dialogue
    4. Produces a final system prompt based on extracted requirements
    5. Returns both the inferred role and the system prompt
    
    Args:
        client: LLM client instance for processing user input
        available_roles: List of available roles in the protocol (e.g., ["Buyer", "Seller", "Shipper"])
                        Can include BSPL Role objects; will be serialized automatically
        context: Optional context about the system/agents (e.g., protocol name)
                Can include BSPL objects; will be serialized automatically
        max_tokens: Maximum tokens for LLM responses
        timeout: Timeout for LLM calls in seconds
    
    Returns:
        Tuple of (inferred_role: str, system_prompt: str) or (None, default_prompt) on failure
    """
    
    print("\n=== Human-in-the-Loop Requirement Extraction ===")
    if context:
        print(f"Protocol/Context: {context}\n")
    if available_roles:
        role_strings = [str(role) for role in available_roles]
        print(f"Available roles: {', '.join(role_strings)}\n")
    
    user_requirements = []
    conversation_history = []
    inferred_role = None
    
    # Initial prompt to gather high-level requirements
    print("Please describe your system requirements and priorities:")
    print("(Type 'done' on a new line when finished)\n")
    
    user_input_lines = []
    while True:
        try:
            line = input()
            if line.strip().lower() == "done":
                break
            user_input_lines.append(line)
        except EOFError:
            break
    
    user_requirements = "\n".join(user_input_lines).strip()
    if not user_requirements:
        default_prompt = "You are a helpful agent. Be thorough and precise in your responses.\n\n**Critical Requirement:**\nWhen selecting or referencing messages within the system, you MUST ALWAYS provide an explicit parameter value for all parameters that are set to None. You should generate this value based on your best understanding of the user requirements."
        return None, default_prompt
    
    # Construct prompt for LLM to extract role and structure requirements
    role_context = ""
    if available_roles:
        role_strings = [str(role) for role in available_roles]
        role_context = f"\n\nAvailable roles in the protocol: {', '.join(role_strings)}. Infer which role best matches the user's stated requirements."
    
    extraction_prompt = f"""The user has provided the following requirements for a multi-agent system:

{user_requirements}{role_context}

Please analyze these requirements and:
1. Infer the most appropriate agent role (if available roles are listed above)
2. Identify the key priorities and constraints
3. Extract specific behavioral guidelines for the agent
4. Note any important decision-making criteria
5. Highlight any system-level goals or constraints

Provide a structured analysis."""
    
    conversation_history.append({"role": "user", "content": extraction_prompt})
    
    try:
        print("[...] Analyzing requirements with LLM...")
        llm_analysis = await call_llm_with_timeout(client, extraction_prompt, timeout=timeout, max_tokens=max_tokens)
    except asyncio.TimeoutError:
        print("Warning: LLM analysis timed out. Using basic requirements.")
        llm_analysis = f"User requirements: {user_requirements}"
    
    conversation_history.append({"role": "assistant", "content": llm_analysis})
    print(f"\nAnalysis:\n{llm_analysis}\n")
    
    # Iterative refinement: ask if user wants to add or modify requirements
    while True:
        print("\nWould you like to refine or add to these requirements? (yes/no)")
        refinement = input().strip().lower()
        
        if refinement not in ["yes", "y"]:
            break
        
        print("Please provide additional requirements or clarifications:")
        additional_lines = []
        while True:
            try:
                line = input()
                if line.strip().lower() == "done":
                    break
                additional_lines.append(line)
            except EOFError:
                break
        
        additional_input = "\n".join(additional_lines).strip()
        if additional_input:
            refinement_prompt = f"""Given the previous analysis, the user has provided additional requirements:

{additional_input}

Please update your analysis to incorporate these new requirements and identify any changes or new priorities."""
            
            conversation_history.append({"role": "user", "content": refinement_prompt})
            
            try:
                print("[...] Refining analysis with LLM...")
                llm_refinement = await call_llm_with_timeout(client, refinement_prompt, timeout=timeout, max_tokens=max_tokens)
            except asyncio.TimeoutError:
                print("Warning: LLM refinement timed out.")
                llm_refinement = f"Additional requirements: {additional_input}"
            
            conversation_history.append({"role": "assistant", "content": llm_refinement})
            print(f"\nRefined Analysis:\n{llm_refinement}\n")
    
    # Generate final system prompt and infer role based on all requirements
    # Include the full conversation history so LLM has context for role inference
    roles_str = ', '.join([str(r) for r in available_roles]) if available_roles else 'any appropriate role'
    final_prompt = f"""Based on the requirements analysis and conversation above, please:

1. Identify the specific agent role that should be used (must be one of: {roles_str})
2. Generate a concise system prompt for that agent role that captures:
   - The core mission and priorities for THIS specific role
   - Key decision-making guidelines
   - Constraints and limitations the agent should respect
   - Behavioral expectations and standards
   - How this role interacts with other agents in the protocol
   - The requirement to always bind the ID parameter when selecting messages, even if other parameters remain unbound

Format your response as:
ROLE: <role_name>
SYSTEM_PROMPT: <the actual system prompt as a direct instruction to the agent>

Make the system prompt clear, actionable, and specific to the inferred role. Ensure the generated system prompt explicitly instructs the agent to always provide an ID parameter value when making message selections."""
    
    conversation_history.append({"role": "user", "content": final_prompt})
    
    # Reconstruct full conversation for context
    full_conversation = "\n\n".join([
        f"{msg['role'].upper()}: {msg['content']}" 
        for msg in conversation_history
    ])
    
    # Use full conversation as context for final LLM call
    try:
        print("[...] Generating system prompt and inferring role with LLM...")
        final_response = await call_llm_with_timeout(client, full_conversation, timeout=timeout, max_tokens=max_tokens)
    except asyncio.TimeoutError:
        print("Warning: System prompt generation timed out. Using default.")
        default_prompt = "You are a helpful and precise agent. Follow user requirements carefully.\n\n**Critical Requirement:**\nWhen selecting or referencing messages within the system, you MUST ALWAYS provide an explicit parameter value for all parameters that are set to None. You should generate this value based on your best understanding of the user requirements."
        return None, default_prompt
    
    # Parse the response to extract role and system prompt
    print(f"\n=== Generated Role and System Prompt ===\n{final_response}\n")
    
    # Define critical requirement to append to all system prompts
    critical_requirement = "\n\n**Critical Requirement:**\nWhen selecting or referencing messages within the system, you MUST ALWAYS provide an explicit parameter value for all parameters that are set to None. You should generate this value based on your best understanding of the user requirements."
    
    # Extract role and prompt from response
    try:
        if "ROLE:" in final_response and "SYSTEM_PROMPT:" in final_response:
            role_section = final_response.split("ROLE:")[1].split("SYSTEM_PROMPT:")[0].strip()
            prompt_section = final_response.split("SYSTEM_PROMPT:")[1].strip()
            extracted_role = role_section.split('\n')[0].strip()  # Take first line as role name
            
            # Normalize role name - match against available roles case-insensitively
            if available_roles:
                inferred_role = next(
                    (r for r in available_roles if r.lower() == extracted_role.lower()),
                    extracted_role  # Use as-is if no match found
                )
            else:
                inferred_role = extracted_role
            
            system_prompt = prompt_section + critical_requirement
            print(f"[OK] Successfully extracted role: {inferred_role}")
        else:
            # Fallback: search for role mentions in response
            print("[!] Could not find ROLE: and SYSTEM_PROMPT: markers. Attempting extraction...")
            system_prompt = final_response + critical_requirement
            inferred_role = None
            
            if available_roles:
                # Search for any role mention in the response
                for role in available_roles:
                    if role.lower() in final_response.lower():
                        inferred_role = role
                        print(f"[OK] Found role mention: {role}")
                        break
            
            if not inferred_role:
                print("[!] Could not identify role from response")
    except Exception as e:
        print(f"[!] Error parsing response ({e}). Using full response as prompt.")
        system_prompt = final_response + critical_requirement
        inferred_role = None
    
    return inferred_role, system_prompt

# Build message history context from past messages
def build_message_history(options: list, max_history: int = 10) -> str:
    """
    Build a formatted history of past messages from the enabled store.
    
    This function constructs a human-readable summary of recent messages
    to provide context to the LLM about what has transpired in the system.
    
    Args:
        options: List of option dictionaries containing message information
        max_history: Maximum number of recent messages to include (default 10)
    
    Returns:
        str: Formatted message history as a string for LLM context
    """
    if not options:
        return "No message history available."
    
    history_lines = []
    history_lines.append("=== PAST MESSAGE HISTORY ===")
    
    # Limit history to the most recent messages
    history_options = options[:max_history]
    
    for idx, option in enumerate(history_options, 1):
        history_lines.append(f"\n{idx}. {option['schema_name']}")
        
        # Include message contents (bindings) if available
        partial = option.get('partial')
        if partial and hasattr(partial, 'bindings') and partial.bindings:
            for param_name, param_value in partial.bindings.items():
                history_lines.append(f"   {param_name}: {param_value}")
    
    history_lines.append(f"\n=== END HISTORY ({len(history_options)} message(s)) ===")
    
    return "\n".join(history_lines)

# Build user prompt for LLM to understand Local State (modify this to not include the system prompt details)
def build_user_prompt(agent_name: str, role_names, options: list, recent_event: dict = None, examples: list = None, include_history: bool = True) -> str:
    lines = []
    lines.append(f"You are agent '{agent_name}'. Choose at most one option, or return null.")
    if role_names:
        # Convert Role objects to strings
        role_strings = [str(role) for role in role_names]
        lines.append(f"Roles: {', '.join(role_strings)}")
    
    # Include message history if requested
    if include_history and options:
        lines.append('')
        lines.append(build_message_history(options, max_history=10))
    
    lines.append('')
    lines.append("Options:")
    for o in options:
        lines.append(f"{o['index']}) {o['schema_name']} - missing params: {o['missing_params']}")
    if recent_event:
        added = recent_event.get("added")
        if added:
            lines.append(f"Recent added count: {len(added)}")
    lines.append('')
    lines.append('Respond with JSON exactly like: {"choice": <index|null>, "params": {"p": "v", ...}}')
    if examples:
        lines.append("Examples:")
        for ex in examples:
            lines.append(json.dumps(ex))
    return "\n".join(lines)

# Call the LLM
async def choose_option_from_llm(client: LLMClient, prompt: str, timeout: float = 30.0, system_prompt: Optional[str] = None) -> Optional[Tuple[Optional[int], Dict[str, Any]]]:
    try:
        text = await call_llm_with_timeout(client, prompt, timeout=timeout, system_prompt=system_prompt)
    except asyncio.TimeoutError:
        return None
    parsed = parse_llm_json_reply(text)
    if not parsed:
        return None
    return parsed["choice"], parsed["params"]

# Prompt the LLM to choose and bid parameters
async def choose_and_bind(adapter, enabled_store, event: dict, client: LLMClient, *, timeout: float):
    """
    - On first call: Executes gather_requirements_from_user to generate a system prompt and infer agent role.
    - Collect enabled Partial objects from `enabled_store.messages()`.
    - Build a detailed user prompt containing enabled messages, roles, schemas, etc.
    - Use the cached system prompt for all LLM calls.
    - Prompt the LLM to pick an index and provide parameters.
    - Validate parameter names, attempt `Partial.bind(**params)`.
    - Return bound Message instance or None.
    """
    global _SYSTEM_PROMPT_CACHE
    # Extract adapter data
    adapter_json = protocol_to_json(adapter)
    adapter_data = json.loads(adapter_json)
    print(f"\n=== Adapter Data ===\n{adapter_data}\n")
    # On first call, gather requirements and generate system prompt
    if _SYSTEM_PROMPT_CACHE is None:
        print("\n=== First-time initialization: Gathering system requirements ===")
        agent_context = f"Protocol context for {adapter_data['name']}"
        available_roles = adapter_data['roles']
        inferred_role, system_prompt = await gather_requirements_from_user(client, available_roles=available_roles, context=agent_context, timeout=timeout)
        _SYSTEM_PROMPT_CACHE = system_prompt
        print(f"Inferred role: {inferred_role}\n")
        print("System prompt cached for future LLM calls.\n")
    
    # Collect enabled Partial objects
    options = []
    idx = 0
    print_enabled_store(enabled_store)
    for p in enabled_store.messages():
        # p is a Partial; missing params = those present but set to None (or not in payload)
        missing = [k for k in p.bindings.keys() if p.bindings.get(k) is None]
        options.append({
            "index": idx,
            "schema_name": p.schema.qualified_name,
            "missing_params": missing,
            "partial": p,
            "sender": p.schema.sender.name,
            "recipients": [r.name for r in p.schema.recipients],
        })
        idx += 1

    if not options:
        return None

    # Build detailed user prompt with enabled messages and agent information
    role_names = adapter_data['roles'] if 'roles' in adapter_data else None
    user_prompt = build_user_prompt(adapter_data['name'], role_names, options, recent_event=event, examples=[
        {"choice": None, "params": {}},
        {"choice": 0, "params": {}},
    ])
    print_user_prompt(user_prompt)
    # Call LLM with cached system prompt
    res = await choose_option_from_llm(client, user_prompt, timeout=timeout, system_prompt=_SYSTEM_PROMPT_CACHE)
    print_llm_response(res) 
    if not res:
        adapter.logger and adapter.logger.debug("LLM returned no usable result")
        return None
    choice_idx, params = res
    if choice_idx is None:
        return None
    if not (0 <= choice_idx < len(options)):
        adapter.logger and adapter.logger.warning(f"LLM chose invalid index: {choice_idx}")
        return None

    chosen_partial = options[choice_idx]["partial"]
    # Validate param names
    for k in params.keys():
        if k not in chosen_partial.schema.parameters:
            adapter.logger and adapter.logger.warning(f"LLM returned unknown parameter '{k}' for {chosen_partial.schema}")
            return None

    try:
        instance = chosen_partial.bind(**params)
    except Exception as exc:
        adapter.logger and adapter.logger.warning(f"Binding failed: {exc}")
        return None

    return instance

if __name__ == "__main__":
    client = AnthropicLLMClient()
    role, prompt = asyncio.run(gather_requirements_from_user(client, available_roles=["Buyer", "Seller", "Shipper"], context="Purchase Protocol"))
    print(f"\n=== Results ===")
    print(f"Inferred Role: {role}")
    print(f"\nSystem Prompt:\n{prompt}")