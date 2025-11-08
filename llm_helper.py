#!/usr/bin/env python3
import asyncio
import json
import os
from typing import Any, Dict, Optional, Tuple
import anthropic
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
async def call_llm_with_timeout(client: LLMClient, prompt: str, timeout: float = 5.0, max_tokens: int = 200, system_prompt: Optional[str] = None) -> str:
    return await asyncio.wait_for(client.complete(prompt, max_tokens=max_tokens, system_prompt=system_prompt), timeout=timeout)


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


# Human-in-the-loop requirement extraction
async def gather_requirements_from_user(client: LLMClient, available_roles: list = None, context: str = "", *, max_tokens: int = 1000, timeout: float = 10.0) -> Tuple[Optional[str], str]:
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
        context: Optional context about the system/agents (e.g., protocol name)
        max_tokens: Maximum tokens for LLM responses
        timeout: Timeout for LLM calls in seconds
    
    Returns:
        Tuple of (inferred_role: str, system_prompt: str) or (None, default_prompt) on failure
    """
    print("\n=== Human-in-the-Loop Requirement Extraction ===")
    if context:
        print(f"Protocol/Context: {context}\n")
    if available_roles:
        print(f"Available roles: {', '.join(available_roles)}\n")
    
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
        return None, "You are a helpful agent. Be thorough and precise in your responses."
    
    # Construct prompt for LLM to extract role and structure requirements
    role_context = ""
    if available_roles:
        role_context = f"\n\nAvailable roles in the protocol: {', '.join(available_roles)}. Infer which role best matches the user's stated requirements."
    
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
        print("⏳ Analyzing requirements with LLM...")
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
                print("⏳ Refining analysis with LLM...")
                llm_refinement = await call_llm_with_timeout(client, refinement_prompt, timeout=timeout, max_tokens=max_tokens)
            except asyncio.TimeoutError:
                print("Warning: LLM refinement timed out.")
                llm_refinement = f"Additional requirements: {additional_input}"
            
            conversation_history.append({"role": "assistant", "content": llm_refinement})
            print(f"\nRefined Analysis:\n{llm_refinement}\n")
    
    # Generate final system prompt and infer role based on all requirements
    # Include the full conversation history so LLM has context for role inference
    final_prompt = f"""Based on the requirements analysis and conversation above, please:

1. Identify the specific agent role that should be used (must be one of: {', '.join(available_roles) if available_roles else 'any appropriate role'})
2. Generate a concise system prompt for that agent role that captures:
   - The core mission and priorities for THIS specific role
   - Key decision-making guidelines
   - Constraints and limitations the agent should respect
   - Behavioral expectations and standards
   - How this role interacts with other agents in the protocol

Format your response as:
ROLE: <role_name>
SYSTEM_PROMPT: <the actual system prompt as a direct instruction to the agent>

Make the system prompt clear, actionable, and specific to the inferred role."""
    
    conversation_history.append({"role": "user", "content": final_prompt})
    
    # Reconstruct full conversation for context
    full_conversation = "\n\n".join([
        f"{msg['role'].upper()}: {msg['content']}" 
        for msg in conversation_history
    ])
    
    # Use full conversation as context for final LLM call
    try:
        print("⏳ Generating system prompt and inferring role with LLM...")
        final_response = await call_llm_with_timeout(client, full_conversation, timeout=timeout, max_tokens=max_tokens)
    except asyncio.TimeoutError:
        print("Warning: System prompt generation timed out. Using default.")
        return None, "You are a helpful and precise agent. Follow user requirements carefully."
    
    # Parse the response to extract role and system prompt
    print(f"\n=== Generated Role and System Prompt ===\n{final_response}\n")
    
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
            
            system_prompt = prompt_section
            print(f"✓ Successfully extracted role: {inferred_role}")
        else:
            # Fallback: search for role mentions in response
            print("⚠ Could not find ROLE: and SYSTEM_PROMPT: markers. Attempting extraction...")
            system_prompt = final_response
            inferred_role = None
            
            if available_roles:
                # Search for any role mention in the response
                for role in available_roles:
                    if role.lower() in final_response.lower():
                        inferred_role = role
                        print(f"✓ Found role mention: {role}")
                        break
            
            if not inferred_role:
                print("⚠ Could not identify role from response")
    except Exception as e:
        print(f"⚠ Error parsing response ({e}). Using full response as prompt.")
        system_prompt = final_response
        inferred_role = None
    
    return inferred_role, system_prompt


# Build user prompt for LLM to understand Local State (modify this to not include the system prompt details)
def build_user_prompt(agent_name: str, role_names, options: list, recent_event: dict = None, examples: list = None) -> str:
    lines = []
    lines.append(f"You are agent '{agent_name}'. Choose at most one option, or return null.")
    if role_names:
        lines.append(f"Roles: {', '.join(role_names)}")
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
async def choose_option_from_llm(client: LLMClient, prompt: str, timeout: float = 5.0, system_prompt: Optional[str] = None) -> Optional[Tuple[Optional[int], Dict[str, Any]]]:
    try:
        text = await call_llm_with_timeout(client, prompt, timeout=timeout, system_prompt=system_prompt)
    except asyncio.TimeoutError:
        return None
    parsed = parse_llm_json_reply(text)
    if not parsed:
        return None
    return parsed["choice"], parsed["params"]


# Prompt the LLM to choose and bid parameters
async def choose_and_bind(adapter, enabled_store, event: dict, client: LLMClient, *, timeout: float = 5.0):
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
    
    # On first call, gather requirements and generate system prompt
    if _SYSTEM_PROMPT_CACHE is None:
        print("\n=== First-time initialization: Gathering system requirements ===")
        agent_context = f"Protocol context for {adapter.name}"
        available_roles = getattr(adapter, "roles", None)
        inferred_role, system_prompt = await gather_requirements_from_user(client, available_roles=available_roles, context=agent_context, timeout=timeout)
        _SYSTEM_PROMPT_CACHE = system_prompt
        print(f"Inferred role: {inferred_role}\n")
        print("System prompt cached for future LLM calls.\n")
    
    # Collect enabled Partial objects
    options = []
    idx = 0
    print("Enabled messages changed.")
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
    role_names = [r for r in adapter.roles] if hasattr(adapter, "roles") else None
    user_prompt = build_user_prompt(adapter.name, role_names, options, recent_event=event, examples=[
        {"choice": None, "params": {}},
        {"choice": 0, "params": {}},
    ])
    
    # Call LLM with cached system prompt
    res = await choose_option_from_llm(client, user_prompt, timeout=timeout, system_prompt=_SYSTEM_PROMPT_CACHE)
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