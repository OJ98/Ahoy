import json
import os
import sys
    
from datetime import datetime
from typing import Dict, List, Any, Optional


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    elif isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    elif isinstance(value, set):
        return sorted([_serialize_value(v) for v in value], key=str)
    elif hasattr(value, 'name'):
        # Handle objects with a 'name' attribute (like BSPL Role, Protocol, etc.)
        return {"__object_type__": value.__class__.__name__, "name": str(value.name)}
    else:
        return str(value)


def _extract_message(message: Any) -> Dict[str, Any]:
    result = {
        "schema_name": message.schema.name,
        "qualified_name": message.schema.qualified_name,
        "payload": _serialize_value(message.payload),
        "key": message.key,
        "meta": _serialize_value(message.meta),
    }
    
    try:
        result["sender"] = message.schema.sender.name if message.schema.sender else None
    except Exception:
        result["sender"] = None
    
    try:
        result["recipients"] = [r.name for r in message.schema.recipients] if message.schema.recipients else []
    except Exception:
        result["recipients"] = []
    
    try:
        result["parameters"] = {
            "ins": sorted(list(message.schema.ins)),
            "outs": sorted(list(message.schema.outs)),
            "nils": sorted(list(message.schema.nils)),
            "keys": sorted(list(message.schema.keys)),
        }
    except Exception:
        result["parameters"] = {}
    
    return result


def _extract_context(context: Any, system_id: Any = None) -> Dict[str, Any]:
    result = {
        "bindings": _serialize_value(context.bindings),
        "messages": [_extract_message(msg) for msg in context._messages.values()],
        "subcontexts": {}
    }
    
    for param_name, param_contexts in context.subcontexts.items():
        result["subcontexts"][param_name] = {}
        for param_value, subcontext in param_contexts.items():
            result["subcontexts"][param_name][_serialize_value(param_value)] = _extract_context(
                subcontext, system_id
            )
    
    return result


def extract_social_state(adapter: Any) -> Dict[str, Any]:
    # Serialize adapter.name properly
    adapter_name = adapter.name if hasattr(adapter, 'name') else 'unknown'
    if hasattr(adapter_name, 'name'):
        # It's a Role or similar object
        serialized_name = _serialize_value(adapter_name)
    else:
        serialized_name = adapter_name
    
    result = {
        "adapter_name": serialized_name,
        "timestamp": datetime.now().isoformat(),
        "systems": {},
        "global_message_count": 0,
        "protocols": [],
        "roles": []
    }
    
    if hasattr(adapter, 'history') and hasattr(adapter.history, 'contexts'):
        for system_id, context in adapter.history.contexts.items():
            root_context = _extract_context(context, system_id)
            
            all_messages = list(adapter.history.messages())
            system_messages = [
                _extract_message(msg) for msg in all_messages 
                if getattr(msg, 'system', None) == system_id
            ]
            
            result["systems"][str(system_id)] = {
                "root_context": root_context,
                "all_messages": system_messages,
                "message_count": len(system_messages)
            }
            
            result["global_message_count"] += len(system_messages)
    
    if hasattr(adapter, 'protocols'):
        for protocol in adapter.protocols:
            try:
                result["protocols"].append(protocol.name)
            except Exception:
                pass
    
    if hasattr(adapter, 'roles'):
        result["roles"] = [_serialize_value(role) for role in adapter.roles]
    
    return result


def extract_social_state_for_message_type(
    adapter: Any, 
    message_type_name: Optional[str] = None
) -> Dict[str, Any]:
    result = {
        "adapter_name": getattr(adapter, 'name', 'unknown'),
        "timestamp": datetime.now().isoformat(),
        "message_type_filter": message_type_name,
        "messages": [],
        "message_count": 0,
        "systems": {}
    }
    
    if hasattr(adapter, 'history'):
        all_messages = list(adapter.history.messages())
        
        for message in all_messages:
            if message_type_name is None or message.schema.name == message_type_name:
                msg_dict = _extract_message(message)
                result["messages"].append(msg_dict)
                
                system_id = str(getattr(message, 'system', 'unknown'))
                if system_id not in result["systems"]:
                    result["systems"][system_id] = 0
                result["systems"][system_id] += 1
        
        result["message_count"] = len(result["messages"])
    
    return result


def social_state_to_json(state_dict: Dict[str, Any], indent: int = 2) -> str:
    """
    Convert a social state dictionary to a JSON string.
    
    Args:
        state_dict: The social state dictionary
        indent: Number of spaces for JSON indentation
    
    Returns:
        JSON string representation of the social state
    """
    return json.dumps(state_dict, indent=indent, default=str)


def get_social_state_json(adapter: Any, indent: int = 2) -> str:
    """
    Extract social state from an adapter and return as JSON string.
    
    Args:
        adapter: The BSPL adapter instance
        indent: Number of spaces for JSON indentation (default 2)
    
    Returns:
        JSON string containing the serialized social state
    """
    state = extract_social_state(adapter)
    return social_state_to_json(state, indent)


def _deserialize_value(value: Any, role_map: Optional[Dict[str, Any]] = None) -> Any:
    """
    Deserialize a value from the social state, reconstructing BSPL objects where possible.
    
    Args:
        value: The value to deserialize
        role_map: Optional mapping of role names to actual Role objects
    
    Returns:
        The deserialized value
    """
    if value is None:
        return None
    elif isinstance(value, bool):
        return value
    elif isinstance(value, (str, int, float)):
        return value
    elif isinstance(value, dict):
        # Check if this is a serialized BSPL object
        if "__object_type__" in value and "name" in value:
            obj_type = value["__object_type__"]
            obj_name = value["name"]
            
            # Try to reconstruct the object based on type and role_map
            if obj_type == "Role" and role_map:
                return role_map.get(obj_name, obj_name)
            else:
                return obj_name
        else:
            # Regular dict - recursively deserialize values
            return {k: _deserialize_value(v, role_map) for k, v in value.items()}
    elif isinstance(value, list):
        return [_deserialize_value(v, role_map) for v in value]
    else:
        return value


def deserialize_social_state(state_dict: Dict[str, Any], role_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Deserialize a social state dictionary, reconstructing BSPL objects.
    
    Args:
        state_dict: The serialized social state dictionary
        role_map: Optional mapping of role names to actual Role objects for reconstruction
    
    Returns:
        Deserialized state dictionary with reconstructed objects
    """
    return _deserialize_value(state_dict, role_map)


def load_social_state_from_json(json_str: str, role_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Load and deserialize a social state from a JSON string.
    
    Args:
        json_str: JSON string representation of social state
        role_map: Optional mapping of role names to actual Role objects for reconstruction
    
    Returns:
        Deserialized state dictionary
    """
    state_dict = json.loads(json_str)
    return deserialize_social_state(state_dict, role_map)


def load_social_state_from_file(filepath: str, role_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Load and deserialize a social state from a file.
    
    Args:
        filepath: Path to the JSON file
        role_map: Optional mapping of role names to actual Role objects for reconstruction
    
    Returns:
        Deserialized state dictionary
    """
    with open(filepath, 'r') as f:
        json_str = f.read()
    return load_social_state_from_json(json_str, role_map)


def save_social_state(adapter: Any, filepath: str, indent: int = 2) -> str:
    """
    Extract social state from adapter and save it to a JSON file.
    
    Args:
        adapter: The BSPL adapter instance
        filepath: Path where the JSON file will be saved
        indent: Number of spaces for JSON indentation (default 2)
    
    Returns:
        The filepath where the state was saved
    """
    json_str = get_social_state_json(adapter, indent)
    
    with open(filepath, 'w') as f:
        f.write(json_str)
    
    return filepath


def main():
    """
    Test the social state extraction functions using the Purchase protocol from purchase.bspl.
    """
    # Add the current directory to sys.path to allow imports
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    try:
        # Import required adapter modules for testing
        from bspl.adapter import Adapter
        from bspl.adapter.core import COLORS
        from configuration import systems, agents, protocol
        from Purchase import Buyer
        
        print("=" * 80)
        print("SOCIAL STATE EXTRACTION TEST - PURCHASE PROTOCOL")
        print("=" * 80)
        
        # Load configuration
        print("\n[SETUP] Loading configuration from configuration.py...")
        try:
            print("✓ Configuration loaded successfully")
            print(f"  - Protocol: {protocol.name}")
            print(f"  - Available systems: {list(systems.keys())}")
            print(f"  - Available agents: {list(agents.keys())}")
        except Exception as e:
            print(f"✗ Error loading configuration: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Instantiate adapter for Buyer role
        print("\n[SETUP] Instantiating Adapter for Buyer role...")
        try:
            adapter = Adapter(Buyer, systems, agents, color=COLORS[0])
            print(f"✓ Adapter instantiated: {adapter.name}")
        except Exception as e:
            print(f"✗ Error instantiating adapter: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Test 1: Extract full social state
        print("\n[TEST 1] Extracting full social state...")
        try:
            social_state = extract_social_state(adapter)
            print("✓ Full social state extracted successfully")
            print(f"  - Adapter: {social_state['adapter_name']}")
            print(f"  - Protocols: {social_state['protocols']}")
            print(f"  - Roles: {social_state['roles']}")
            print(f"  - Global message count: {social_state['global_message_count']}")
            print(f"  - Systems: {list(social_state['systems'].keys())}")
        except Exception as e:
            print(f"✗ Error extracting full social state: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 2: Extract messages by type
        print("\n[TEST 2] Extracting messages by type...")
        try:
            messages_state = extract_social_state_for_message_type(adapter)
            print("✓ Messages extracted successfully")
            print(f"  - Message count: {messages_state['message_count']}")
            print(f"  - Systems: {messages_state['systems']}")
        except Exception as e:
            print(f"✗ Error extracting messages: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 3: Serialize to JSON
        print("\n[TEST 3] Serializing social state to JSON...")
        try:
            json_str = get_social_state_json(adapter)
            print("✓ Social state serialized to JSON successfully")
            print(f"  - JSON length: {len(json_str)} characters")
            parsed = json.loads(json_str)
            print(f"  - Top-level keys: {list(parsed.keys())}")
        except Exception as e:
            print(f"✗ Error serializing to JSON: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 4: Save to file
        print("\n[TEST 4] Saving social state to file...")
        try:
            filepath = os.path.join(current_dir, "test_social_state.json")
            saved_path = save_social_state(adapter, filepath)
            if os.path.exists(saved_path):
                file_size = os.path.getsize(saved_path)
                print(f"✓ Social state saved successfully")
                print(f"  - File path: {saved_path}")
                print(f"  - File size: {file_size} bytes")
            else:
                print(f"✗ File was not created")
        except Exception as e:
            print(f"✗ Error saving social state: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 5: Load and deserialize from file
        print("\n[TEST 5] Loading and deserializing social state from file...")
        try:
            filepath = os.path.join(current_dir, "test_social_state.json")
            
            # Create a role map for deserialization
            role_map = {}
            for role_obj in systems["Purchase"]["roles"].keys():
                if hasattr(role_obj, 'name'):
                    role_map[role_obj.name] = role_obj
            
            loaded_state = load_social_state_from_file(filepath, role_map=role_map)
            print("✓ Social state loaded and deserialized successfully")
            print(f"  - Adapter: {loaded_state['adapter_name']}")
            print(f"  - Protocols: {loaded_state['protocols']}")
            print(f"  - Roles: {loaded_state['roles']}")
            print(f"  - Global message count: {loaded_state['global_message_count']}")
        except Exception as e:
            print(f"✗ Error loading social state: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 80)
        print("TESTS COMPLETED")
        print("=" * 80)
    
    except ImportError as e:
        print(f"\nX Import Error: {e}")
        print("Make sure you have the BSPL library installed and the purchase.bspl file exists.")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\nX Unexpected Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
