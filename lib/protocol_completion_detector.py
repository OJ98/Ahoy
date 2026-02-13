#!/usr/bin/env python3
"""
Protocol Completion Detector - Identify final messages per role.
Auto-detects when a role has completed its protocol participation.
"""

from typing import Dict, Optional, Any
from pathlib import Path
from lib.protocol_discovery import get_protocol_structure





def extract_completion_rule_from_protocol(protocol_name: str, role_name: str) -> Optional[tuple]:
    """
    Extract completion rule for a role using LLM analysis of BSPL protocol.
    
    Asks the LLM: "What message type and count indicates completion for this role?"
    Returns: (message_type, "send" or "receive", count)
    
    Example:
        - (Packed, "receive", 4) = Role completes when 4 Packed messages are received
        - (RequestWrapping, "send", 4) = Role completes when 4 RequestWrapping messages are sent
    
    Args:
        protocol_name: Name of protocol to analyze
        role_name: Name of role within the protocol
    
    Returns:
        Tuple of (message_type, direction, count) or None if extraction fails
    """
    try:
        from lib.llm_client import AnthropicLLMClient
        import asyncio
        import json
        
        # Read BSPL protocol file
        protocol_file = Path(__file__).resolve().parent.parent / "protocols" / f"{protocol_name.lower()}.bspl"
        
        if not protocol_file.exists():
            return None
        
        protocol_spec = protocol_file.read_text()
        
        # Try to read user input to understand item count
        input_file = Path(__file__).resolve().parent.parent / "input.txt"
        user_instructions = ""
        if input_file.exists():
            user_instructions = input_file.read_text()
        
        # Create LLM client
        llm = AnthropicLLMClient()
        
        prompt = (
            f"""Analyze this BSPL protocol and user instructions to determine the completion rule for the {role_name} role in the {protocol_name} protocol.

USER REQUIREMENTS:
```
{user_instructions}
```

BSPL PROTOCOL:
```
{protocol_spec}
```

COMPLETION RULE FORMAT:
Return a JSON with:
- "protocol": The protocol name (should be "{protocol_name}")
- "role": The role name (should be "{role_name}")
- "message_type": The message that indicates role completion (e.g., "Packed", "Labeled", "RequestWrapping")
- "direction": Either "send" (role sends the message) or "receive" (role receives the message)
- "count": How many of that message type indicates completion for this role

ANALYSIS PROCESS:
1. Count how many items/orders are specified in the user requirements
2. Determine which message type marks completion for {role_name}
3. The count should equal the number of items/orders to process

EXAMPLE RESPONSES:
{{"protocol": "Logistics", "role": "Merchant", "message_type": "Packed", "direction": "receive", "count": 4}}  // Merchant completes after receiving 4 Packed messages
{{"protocol": "Purchase", "role": "Buyer", "message_type": "completed", "direction": "send", "count": 3}}  // Buyer completes after sending 3 completed messages

Based on the user requirements and protocol structure, return ONLY the JSON completion rule (no explanation):"""
        )
        
        # Run async complete method
        response = asyncio.run(llm.complete(prompt=prompt))
        
        # Parse the JSON response
        import json
        import re
        
        response_stripped = response.strip()
        
        # Extract JSON
        if '```json' in response_stripped:
            json_part = response_stripped.split('```json')[1].split('```')[0]
        elif '```' in response_stripped:
            json_part = response_stripped.split('```')[1].split('```')[0]
        else:
            json_part = response_stripped
        
        # Find JSON object
        json_start = json_part.find('{')
        json_end = json_part.rfind('}')
        
        if json_start != -1 and json_end != -1 and json_start < json_end:
            json_str = json_part[json_start:json_end+1]
            try:
                rule = json.loads(json_str)
                protocol = rule.get('protocol', protocol_name)
                role = rule.get('role', role_name)
                message_type = rule.get('message_type')
                direction = rule.get('direction')
                count = rule.get('count')
                
                # Ensure count is an integer
                if isinstance(count, str):
                    try:
                        count = int(count)
                    except (ValueError, TypeError):
                        return None
                
                if message_type and direction in ['send', 'receive'] and isinstance(count, int) and count > 0:
                    return (message_type, direction, count, protocol, role)
                else:
                    return None
            except json.JSONDecodeError:
                return None
        
        return None
    except Exception:
        return None


async def extract_event_completion_rule(
    protocol_name: str,
    role_name: str,
    event_message: str,
    event_metadata: Dict[str, Any]
) -> Optional[tuple]:
    """
    Extract completion rule for a specific external event.
    
    Similar to extract_completion_rule_from_protocol, but customized for a specific event.
    Asks the LLM: "What message type and count indicates completion for THIS SPECIFIC EVENT?"
    
    This is an async function - call it with await when used within async context.
    
    Args:
        protocol_name: Name of protocol
        role_name: Name of role in this protocol
        event_message: Event description (e.g., "Purchase request: Buy a bat")
        event_metadata: Event metadata dict (e.g., {"item": "bat", "budget": 29.99})
    
    Returns:
        Tuple of (message_type, direction, count) or None if extraction fails
    """
    try:
        from lib.llm_client import AnthropicLLMClient
        import json
        
        # Read BSPL protocol file
        protocol_file = Path(__file__).resolve().parent.parent / "protocols" / f"{protocol_name.lower()}.bspl"
        
        if not protocol_file.exists():
            return None
        
        protocol_spec = protocol_file.read_text()
        
        # Create LLM client
        llm = AnthropicLLMClient()
        
        # Format metadata for readability
        metadata_str = "\n".join([f"  - {k}: {v}" for k, v in event_metadata.items()])
        
        prompt = (
            f"""Analyze this BSPL protocol and external event to determine the completion rule.

EXTERNAL EVENT:
Event: {event_message}
Metadata:
{metadata_str}

PROTOCOL ROLE BEING CALLED:
Protocol: {protocol_name}
Role: {role_name}

BSPL PROTOCOL:
```
{protocol_spec}
```

TASK: Determine what message indicates completion for this SPECIFIC EVENT in the {role_name} role.

For example, if {role_name} receives a request to process items, what message type and count indicates that all items were processed?

Return ONLY the JSON completion rule:
{{"role": "{role_name}", "message_type": "MessageType", "direction": "send|receive", "count": 1}}

Where:
- message_type: The specific message type that indicates completion for THIS EVENT
- direction: "send" (role sends) or "receive" (role receives)
- count: For this ONE event request, how many of this message type is needed?

Get the count from the event - if buying 1 bat, count is typically 1. If buying 3 items, count is 3.

Return JSON only:"""
        )
        
        # Await the async complete method
        response = await llm.complete(prompt=prompt)
        
        # Parse JSON response
        response_stripped = response.strip()
        
        if '```json' in response_stripped:
            json_part = response_stripped.split('```json')[1].split('```')[0]
        elif '```' in response_stripped:
            json_part = response_stripped.split('```')[1].split('```')[0]
        else:
            json_part = response_stripped
        
        json_start = json_part.find('{')
        json_end = json_part.rfind('}')
        
        if json_start != -1 and json_end != -1 and json_start < json_end:
            json_str = json_part[json_start:json_end+1]
            try:
                rule = json.loads(json_str)
                message_type = rule.get('message_type')
                direction = rule.get('direction')
                count = rule.get('count')
                
                # Ensure count is an integer
                if isinstance(count, str):
                    try:
                        count = int(count)
                    except (ValueError, TypeError):
                        return None
                
                if message_type and direction in ['send', 'receive'] and isinstance(count, int) and count > 0:
                    return (message_type, direction, count, protocol_name, role_name)
                else:
                    return None
            except json.JSONDecodeError:
                return None
        
        return None
    except Exception:
        return None
    """
    Extract completion rule for a role using LLM analysis of BSPL protocol.
    
    Asks the LLM: "What message type and count indicates completion for this role?"
    Returns: (message_type, "send" or "receive", count)
    
    Example:
        - (Packed, "receive", 4) = Role completes when 4 Packed messages are received
        - (RequestWrapping, "send", 4) = Role completes when 4 RequestWrapping messages are sent
    
    Args:
        protocol_name: Name of protocol to analyze
        role_name: Name of role within the protocol
    
    Returns:
        Tuple of (message_type, direction, count) or None if extraction fails
    """
    try:
        from lib.llm_client import AnthropicLLMClient
        import asyncio
        import json
        
        # Read BSPL protocol file
        protocol_file = Path(__file__).resolve().parent.parent / "protocols" / f"{protocol_name.lower()}.bspl"
        
        if not protocol_file.exists():
            return None
        
        protocol_spec = protocol_file.read_text()
        
        # Try to read user input to understand item count
        input_file = Path(__file__).resolve().parent.parent / "input.txt"
        user_instructions = ""
        if input_file.exists():
            user_instructions = input_file.read_text()
        
        # Create LLM client
        llm = AnthropicLLMClient()
        
        prompt = (
            f"""Analyze this BSPL protocol and user instructions to determine the completion rule for the {role_name} role in the {protocol_name} protocol.

USER REQUIREMENTS:
```
{user_instructions}
```

BSPL PROTOCOL:
```
{protocol_spec}
```

COMPLETION RULE FORMAT:
Return a JSON with:
- "protocol": The protocol name (should be "{protocol_name}")
- "role": The role name (should be "{role_name}")
- "message_type": The message that indicates role completion (e.g., "Packed", "Labeled", "RequestWrapping")
- "direction": Either "send" (role sends the message) or "receive" (role receives the message)
- "count": How many of that message type indicates completion for this role

ANALYSIS PROCESS:
1. Count how many items/orders are specified in the user requirements
2. Determine which message type marks completion for {role_name}
3. The count should equal the number of items/orders to process

EXAMPLE RESPONSES:
{{"protocol": "Logistics", "role": "Merchant", "message_type": "Packed", "direction": "receive", "count": 4}}  // Merchant completes after receiving 4 Packed messages
{{"protocol": "Purchase", "role": "Buyer", "message_type": "completed", "direction": "send", "count": 3}}  // Buyer completes after sending 3 completed messages

Based on the user requirements and protocol structure, return ONLY the JSON completion rule (no explanation):"""
        )
        
        # Run async complete method
        response = asyncio.run(llm.complete(prompt=prompt))
        
        # Parse the JSON response
        import json
        import re
        
        response_stripped = response.strip()
        
        # Extract JSON
        if '```json' in response_stripped:
            json_part = response_stripped.split('```json')[1].split('```')[0]
        elif '```' in response_stripped:
            json_part = response_stripped.split('```')[1].split('```')[0]
        else:
            json_part = response_stripped
        
        # Find JSON object
        json_start = json_part.find('{')
        json_end = json_part.rfind('}')
        
        if json_start != -1 and json_end != -1 and json_start < json_end:
            json_str = json_part[json_start:json_end+1]
            try:
                rule = json.loads(json_str)
                protocol = rule.get('protocol', protocol_name)
                role = rule.get('role', role_name)
                message_type = rule.get('message_type')
                direction = rule.get('direction')
                count = rule.get('count')
                
                # Ensure count is an integer
                if isinstance(count, str):
                    try:
                        count = int(count)
                    except (ValueError, TypeError):
                        return None
                
                if message_type and direction in ['send', 'receive'] and isinstance(count, int) and count > 0:
                    return (message_type, direction, count, protocol, role)
                else:
                    return None
            except json.JSONDecodeError:
                return None
        
        return None
    except Exception:
        return None


def extract_request_response_from_protocol(protocol_name: str) -> Dict[str, str]:
    """
    Analyze BSPL protocol structure using LLM to extract request-response message mappings.
    
    Reads the BSPL protocol file and uses Claude to identify which request messages
    correspond to which completion/response messages.
    
    Args:
        protocol_name: Name of protocol (e.g., "Logistics")
    
    Returns:
        dict: Mapping of completion_msg_type -> request_msg_type
    """
    try:
        from pathlib import Path
        import asyncio
        
        # Read the BSPL protocol file
        protocol_file = Path(__file__).parent.parent / "protocols" / f"{protocol_name.lower()}.bspl"
        if not protocol_file.exists():
            return {}
        
        protocol_spec = protocol_file.read_text()
        
        # Use LLM to analyze the protocol
        from lib.llm_client import AnthropicLLMClient
        
        llm = AnthropicLLMClient()
        
        prompt = (
            f"""You are a protocol analyzer. Analyze this BSPL protocol and create a JSON mapping.

TASK: For each message that represents a completion/response (like Packed, Wrapped, Labeled), identify the REQUEST message that triggers it.

Rules:
- Request messages: ones that INITIATE work (RequestWrapping, RequestLabel, etc)
- Response messages: ones that COMPLETE work (Wrapped, Labeled, Packed, etc)
- Each response comes after its corresponding request

OUTPUT: Return ONLY a valid JSON object, nothing else.
Format: {{"response_message": "request_message", ...}}

Example:
{{"Wrapped": "RequestWrapping", "Labeled": "RequestLabel", "Packed": "RequestWrapping"}}

Protocol:
```
{protocol_spec}
```

RESPONSE (JSON ONLY):"""
        )
        
        # Run async complete method
        response = asyncio.run(llm.complete(prompt=prompt))
        
        # Parse the JSON response - be more robust
        import json
        import re
        
        response_stripped = response.strip()
        
        # Try to extract and parse JSON
        # First attempt: look for complete JSON object with curly braces
        # Handle case where LLM wraps response in markdown code blocks
        if '```json' in response_stripped:
            json_part = response_stripped.split('```json')[1].split('```')[0]
        elif '```' in response_stripped:
            json_part = response_stripped.split('```')[1].split('```')[0]
        else:
            json_part = response_stripped
        
        # Find JSON object in the text
        json_start = json_part.find('{')
        json_end = json_part.rfind('}')
        
        if json_start != -1 and json_end != -1 and json_start < json_end:
            json_str = json_part[json_start:json_end+1]
            try:
                mapping = json.loads(json_str)
                return mapping
            except json.JSONDecodeError:
                pass
        
        return {}
    except Exception:
        return {}
