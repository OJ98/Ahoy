#!/usr/bin/env python3

import asyncio
import json
import logging
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from os import getpid

import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
import bspl.adapter.receiver as _recv

# Import the helper modules
from lib import (
    AnthropicLLMClient,
    choose_and_bind,
    UserInterface,
    setup_logging,
    log_debug,
    shutdown_watcher,
    reset_optimization_caches,
)
from lib.llm_client import initialize_llm_tracker, get_llm_tracker
from lib.agent_notes import get_agent_notes, reset_agent_notes
from lib.protocol_completion_detector import (
    is_completion_message, 
    get_completion_message, 
    get_request_message_for_completion,
    extract_completion_rule_from_protocol
)
from lib.dynamic_adapter_manager import create_adapter_for_role, create_adapter_for_agent, get_color_for_protocol_role

# Set global timeout
TIMEOUT = 30.0

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

# Initialize logging system
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = str(LOG_DIR / f"generic_agent_debug_{timestamp}.log")

debug_logger, console_logger = setup_logging(log_filename, mode='a')

# Reset optimization caches at session start for fresh state
reset_optimization_caches()

# Single adapter instance that handles all roles for the agent
# (via agent_identity, the adapter automatically resolves all roles the agent plays)
adapter = None
assigned_agent_identity = None  # Agent identity string (e.g., "Buyer", "Wrapper")
assigned_roles_list = []  # List of (protocol, role) tuples this agent plays
assigned_protocol = None  # First protocol (for backward compat)
assigned_role = None  # First role (for backward compat)
protocol_completion_rules = {}  # Dict mapping (protocol, role) -> completion rule (message_type, direction, count)

# Suppress adapter's internal logging to console
adapter_logger = logging.getLogger("bspl")
adapter_logger.setLevel(logging.CRITICAL)
adapter_logger.propagate = False

# Instantiate the user interface
ui = UserInterface()

# Instantiate the LLM client
llm_client = AnthropicLLMClient()

# Global counters for transaction statistics
transactions = 0


def _register_enabled_message_handlers():
    """
    Dynamically register @adapter.enabled() handlers for send messages if needed.
    
    Note: With the updated llm_decision handler that handles InitEvent,
    this is optional. The decision handler will consult LLM even with no enabled messages.
    """
    log_debug("DEBUG: Enabled message handler registration (optional with InitEvent handling)")


def _initialize_protocol_analysis(protocol_name: str, role_name: str):
    """
    Initialize protocol analysis by extracting completion rule using LLM.
    This is called once per role at agent startup to make completion detection protocol-agnostic.
    
    Completion rule format: (message_type, direction, count)
    Example: ("Packed", "receive", 4) = complete when 4 Packed messages received
    
    Args:
        protocol_name: Name of the protocol to analyze
        role_name: Name of the role to complete
    """
    global protocol_completion_rules
    
    try:
        log_debug(f"Extracting completion rule for {protocol_name}/{role_name} using LLM...")
        rule = extract_completion_rule_from_protocol(protocol_name, role_name)
        
        if rule:
            protocol_completion_rules[(protocol_name, role_name)] = rule
            msg_type, direction, count = rule
            log_debug(f"Successfully extracted completion rule for {protocol_name}/{role_name}: {msg_type} {direction} x{count}")
        else:
            log_debug(f"LLM extraction failed for {protocol_name}/{role_name}, will use hardcoded rules")
    except Exception as e:
        log_debug(f"Error during protocol analysis for {protocol_name}/{role_name}: {e}")
        log_debug(f"Will use hardcoded rules as fallback")


def _validate_enabled_store(enabled_store):
    """
    Validate that enabled_store has messages available.

    Args:
        enabled_store: The adapter's enabled store object

    Returns:
        tuple: (is_valid, messages_list)
    """
    if not enabled_store:
        log_debug("DEBUG: No enabled_store available, skipping decision")
        return False, []

    messages = list(enabled_store.messages())
    log_debug(f"DEBUG: Found {len(messages)} enabled messages")

    if not messages:
        log_debug("DEBUG: No enabled messages available, skipping decision")
        return False, []

    return True, messages


def _check_threshold():
    """
    Check if LLM call threshold has been exceeded.

    Returns:
        tuple: (should_continue, threshold_reason) where should_continue is bool
    """
    tracker = get_llm_tracker()
    if not tracker:
        return True, None

    exceeded, reason = tracker.check_threshold_exceeded()
    if exceeded:
        log_debug(f"Threshold exceeded: {reason}")
        ui.error(f"Threshold exceeded: {reason}")
        ui.divider()
        return False, reason

    return True, None


def _update_llm_status():
    """Display current LLM call status and elapsed time."""
    tracker = get_llm_tracker()
    if tracker:
        status = tracker.get_status()
        ui.status_update(tracker.call_count, tracker.get_elapsed_seconds())
        log_debug(f"Status: {status}")


def _handle_role_completion(instance):
    """
    Handle role completion by creating stop signal.
    
    Args:
        instance: The completed message instance
    
    Raises:
        SystemExit: Always raises to signal completion
    """
    try:
        STOP_SIGNAL_PATH.write_text("transaction_complete")
        log_debug(f"Stop signal created - role {assigned_role} in {assigned_protocol} completed")
    except Exception as e:
        log_debug(f"Error creating stop signal: {e}")
    
    raise SystemExit(f"✅ Goal achieved: {assigned_role} completed in {assigned_protocol}. {instance}")


async def main():
    """
    Main entry point: Waits for protocol(s) to complete.
    Single adapter handles all roles for the agent.
    """
    try:
        if len(assigned_roles_list) == 1:
            protocol, role = assigned_roles_list[0]
            log_debug(f"Generic agent ready for {protocol}.{role} (agent: {assigned_agent_identity}). Waiting for protocol events...")
        else:
            roles_str = ", ".join([f"{r}({p})" for p, r in assigned_roles_list])
            log_debug(f"Generic agent ready for multiple roles: {roles_str}. Waiting for protocol events...")
        
        # Keep the adapter running until protocol completes
        # The decision handler will be called on InitEvent to send initial messages if needed
        await shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH))
    
    except SystemExit:
        raise  # Let completion signals propagate
    except Exception as e:
        log_debug(f"Error in main: {e}")
        ui.error_occurred(str(e))
        raise


def _check_for_received_completion_message(adapter_ref):
    """
    Protocol-agnostic completion detection using LLM-determined rule.

    The LLM analyzes the protocol and determines:
    - What message type indicates completion
    - Whether to count sent or received instances
    - How many are needed for completion

    Rule format: (message_type, "send"|"receive", count)
    Example: ("Packed", "receive", 4) = complete when 4 Packed messages received

    Args:
        adapter_ref: The BSPL adapter instance

    Returns:
        tuple: (is_completed, message_info) where message_info is the completion message details
    """
    try:
        from lib.state_manager import extract_social_state
        
        # Use dynamically extracted rule if available, otherwise use hardcoded
        # For multi-role support, check the primary role first
        rule = protocol_completion_rules.get((assigned_protocol, assigned_role))
        if not rule:
            # Fallback to hardcoded rules - but we need to determine the counter manually
            completion_msg_type = get_completion_message(assigned_protocol, assigned_role)
            if not completion_msg_type:
                log_debug(f"DEBUG: No completion rule defined for {assigned_protocol}/{assigned_role}")
                return False, None
            
            # Try to infer from hardcoded mapping
            request_msg_type = get_request_message_for_completion(assigned_protocol, completion_msg_type)
            if request_msg_type:
                rule = (completion_msg_type, "receive", None)  # Count-based on requests
            else:
                log_debug(f"DEBUG: Cannot determine completion rule for {completion_msg_type}")
                return False, None
        
        message_type, direction, target_count = rule
        
        social_state = extract_social_state(adapter_ref)
        
        # Get all messages from all systems
        all_messages = []
        for system_id, system_data in social_state.get("systems", {}).items():
            all_messages.extend(system_data.get("all_messages", []))
        
        log_debug(f"DEBUG: Checking for completion: {message_type} ({direction}) x{target_count}")
        log_debug(f"DEBUG: Total messages in history: {len(all_messages)}")
        
        # Get our role name for comparison
        our_role_name = adapter_ref.name if hasattr(adapter_ref, 'name') else str(assigned_role)
        if hasattr(our_role_name, 'name'):
            our_role_name = our_role_name.name
        
        log_debug(f"DEBUG: Our role: {our_role_name}, looking for message_type: {message_type}")
        
        # Count messages based on direction
        if direction == "send":
            # Count messages SENT BY our role
            sent_count = 0
            for msg in all_messages:
                if msg.get("schema_name", "").lower() == message_type.lower():
                    sender = msg.get("sender")
                    if sender and str(sender).lower() == str(our_role_name).lower():
                        sent_count += 1
                        log_debug(f"DEBUG:   → Found sent {message_type} from {sender}")
            
            log_debug(f"DEBUG: {message_type} sent by us: {sent_count}, need {target_count}")
            
            if sent_count >= target_count:
                log_debug(f"DEBUG: ✓ Role {assigned_role} completed: sent {sent_count} {message_type} messages")
                return True, None
            else:
                log_debug(f"DEBUG: Role {assigned_role} waiting: {sent_count}/{target_count} {message_type} messages sent")
                return False, None
        
        elif direction == "receive":
            # Count messages RECEIVED BY our role (sender is NOT our role)
            received_count = 0
            for msg in all_messages:
                if msg.get("schema_name", "").lower() == message_type.lower():
                    sender = msg.get("sender")
                    # Message is "received" if sender is NOT us
                    if not sender or str(sender).lower() != str(our_role_name).lower():
                        received_count += 1
                        log_debug(f"DEBUG:   → Found received {message_type} from {sender}")
            
            log_debug(f"DEBUG: {message_type} received by us: {received_count}, need {target_count}")
            
            if received_count >= target_count:
                log_debug(f"DEBUG: ✓ Role {assigned_role} completed: received {received_count} {message_type} messages")
                return True, None
            else:
                log_debug(f"DEBUG: Role {assigned_role} waiting: {received_count}/{target_count} {message_type} messages received")
                return False, None
        else:
            log_debug(f"DEBUG: Unknown direction: {direction}")
            return False, None
            
    except Exception as e:
        log_debug(f"Error checking for received completion: {e}")
        import traceback
        log_debug(f"Traceback: {traceback.format_exc()}")
        return False, None


async def _get_llm_decision_handler():
    """
    Return the LLM decision handler as an async function.
    This is called after adapter is created so we can decorate it.
    """
    async def llm_decision(enabled_store, event):
        """
        LLM decision handler triggered by adapter on protocol state change.
        """
        from bspl.adapter.event import InitEvent
        
        # For multirole adapters, determine which protocol/role this event is for
        # by examining the enabled messages
        current_protocol = assigned_protocol
        current_role = assigned_role
        
        # Try to detect the protocol from enabled messages
        if len(assigned_roles_list) > 1:  # Multirole case
            try:
                # Get first message to determine protocol
                for msg in enabled_store.messages():
                    if hasattr(msg, 'system'):
                        # The system attribute is a Protocol object, get its name
                        msg_system = msg.system
                        msg_system_name = msg_system.name if hasattr(msg_system, 'name') else str(msg_system)
                        
                        # Find matching protocol in our assigned roles
                        for proto, role in assigned_roles_list:
                            if proto == msg_system_name:
                                current_protocol = proto
                                current_role = role
                                log_debug(f"DEBUG: Detected protocol/role from enabled message: {proto}/{role}")
                                break
                        break
            except Exception as e:
                log_debug(f"DEBUG: Could not detect protocol from enabled_store: {e}")
                import traceback
                log_debug(f"Traceback: {traceback.format_exc()}")
        
        log_debug(f"DEBUG: llm_decision called for {current_protocol}.{current_role}")
        log_debug(f"  - enabled_store type: {type(enabled_store)}")
        log_debug(f"  - event type: {type(event)}")
        
        # PROTOCOL-AGNOSTIC: Check for received completion BEFORE consulting LLM
        # This allows roles that complete by receiving a message to exit properly
        is_completed, completion_msg = _check_for_received_completion_message(adapter)
        if is_completed:
            log_debug(f"DEBUG: Role {current_role} completed by RECEIVING: {completion_msg}")
            _handle_role_completion(completion_msg)
        
        # For InitEvent with no enabled messages, still try to get LLM decision for initial sends
        is_init_event = isinstance(event, InitEvent)
        if is_init_event:
            log_debug(f"DEBUG: InitEvent detected for {current_protocol}.{current_role}")
        
        # Validate enabled_store and retrieve messages
        is_valid, messages = _validate_enabled_store(enabled_store)
        
        # For InitEvent with no enabled messages, still consult LLM for initial sends
        if not is_valid:
            if is_init_event:
                log_debug(f"DEBUG: No enabled messages on InitEvent, but still consulting LLM for initial sends")
                # Set empty list so choose_and_bind can handle LLM deciding on initial messages
                messages = []
                is_valid = True  # Mark as valid to proceed to LLM
            else:
                log_debug(f"DEBUG: No enabled messages and not InitEvent, returning")
                return None
        
        log_debug("LLM decision invoked, consulting LLM...")
        
        # Check threshold before making LLM call
        should_continue, reason = _check_threshold()
        if not should_continue:
            raise SystemExit(f"Graceful termination: {reason}")
        
        # Call LLM to decide on available messages (or initial sends for InitEvent)
        log_debug("Consulting LLM for decision...")
        instance = await choose_and_bind(
            adapter=adapter,
            enabled_store=enabled_store,
            event=event,
            client=llm_client,
            timeout=TIMEOUT,
            logger_callback=log_debug,
            current_protocol=current_protocol,
            current_role=current_role,
            all_roles_list=assigned_roles_list
        )
        
        # Display status after LLM call
        _update_llm_status()
        
        # Check threshold after making LLM call
        should_continue, reason = _check_threshold()
        if not should_continue:
            raise SystemExit(f"Graceful termination: {reason}")
        
        log_debug(f"DEBUG: choose_and_bind returned: {instance}")
        
        if instance is None:
            log_debug("DEBUG: No instance returned from LLM, skipping")
            # Before giving up, check if we've received a completion message
            is_completed, completion_msg = _check_for_received_completion_message(adapter)
            if is_completed:
                log_debug(f"DEBUG: Role completed by receiving: {completion_msg}")
                _handle_role_completion(completion_msg)
            
            # If LLM deferred choice for tools, we need to retry the decision
            # This allows the LLM to make a message choice on the next call with tool results available
            # Return None to skip this event, and adapter will check again
            return None

        log_debug(f"DEBUG: Sending message: {instance}")
        
        # Check if this message completes the role (sent messages)
        if hasattr(instance, 'schema') and hasattr(instance.schema, 'name'):
            msg_type = instance.schema.name
            if is_completion_message(assigned_protocol, assigned_role, msg_type):
                _handle_role_completion(instance)
        
        return instance
    
    return llm_decision





def _initialize_tracking_systems():
    """Initialize LLM call tracker."""
    initialize_llm_tracker(max_calls=50, max_duration_seconds=300.0)
    log_debug("LLM tracker initialized: max 20 calls or 3 minutes")


def _cleanup_logging():
    """Close all logging handlers."""
    for handler in debug_logger.handlers:
        handler.close()
    for handler in console_logger.handlers:
        handler.close()


async def _initialize_protocol_and_role():
    """
    Read protocol and role(s) from CHIPS config file.
    
    The CHIPS config provides protocol:role pair(s). This function:
    1. Parses the config (single-role or multi-role JSON format)
    2. Determines which agent plays all these roles
    3. Returns agent identity and list of roles
    
    Note: With the new architecture, a single adapter handles all roles for one agent.
    The adapter automatically manages all roles that agent is configured to play.
    
    Returns:
        tuple: (agent_identity, roles_list) where roles_list is [(protocol, role), ...]
               or (None, []) on failure
    """
    global assigned_protocol, assigned_role, adapter
    
    log_debug("INITIALIZATION PHASE: Reading CHIPS config and determining agent identity")
    
    try:
        # Read CHIPS config file from temp directory
        config_file = Path(tempfile.gettempdir()) / "maf_chips_config.txt"
        
        # DEBUG: Print temp directory and check if file exists
        log_debug(f"DEBUG: Temp directory = {Path(tempfile.gettempdir())}")
        log_debug(f"DEBUG: Looking for config file at: {config_file}")
        
        if not config_file.exists():
            log_debug(f"Config file not found: {config_file}")
            log_debug("Please run 'python chips.py' first to configure protocol and role")
            # DEBUG: List files in temp directory
            temp_dir = Path(tempfile.gettempdir())
            if temp_dir.exists():
                files = list(temp_dir.glob("maf_*.txt"))
                log_debug(f"DEBUG: Files matching 'maf_*.txt' in {temp_dir}: {[f.name for f in files]}")
            return None, []
        
        # Read config and remove BOM if present (UTF-8 with BOM writes '\ufeff' as first char)
        config_content = config_file.read_text().strip()
        if config_content.startswith('\ufeff'):
            config_content = config_content[1:]
        log_debug(f"Read config: {config_content}")
        
        roles_list = []
        explicit_agent_identity = None
        
        # Try parsing as JSON (multi-role format)
        try:
            if config_content.startswith('{'):
                import json
                config_data = json.loads(config_content)
                
                # Check for explicit agent identity (useful for multiprotocol scenarios)
                if "agent" in config_data:
                    explicit_agent_identity = config_data["agent"].strip()
                    log_debug(f"CHIPS config specifies agent identity: {explicit_agent_identity}")
                
                if "roles" in config_data:
                    for role_entry in config_data["roles"]:
                        protocol_name = role_entry.get("protocol", "").strip()
                        role_name = role_entry.get("role", "").strip()
                        if protocol_name and role_name:
                            roles_list.append((protocol_name, role_name))
                    
                    if roles_list:
                        log_debug(f"CHIPS config (JSON): {roles_list}")
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Fall back to simple "Protocol:Role" format (backward compatible)
        if not roles_list:
            parts = config_content.split(':')
            if len(parts) != 2:
                log_debug(f"Invalid config format: {config_content}")
                return None, []
            
            protocol_name = parts[0].strip()
            role_name = parts[1].strip()
            roles_list = [(protocol_name, role_name)]
            
            log_debug(f"CHIPS config (simple): {protocol_name}:{role_name}")
        
        # If explicit agent identity is provided, use it directly
        if explicit_agent_identity:
            log_debug(f"Using explicit agent identity from config: {explicit_agent_identity}")
            assigned_roles = roles_list
            return explicit_agent_identity, assigned_roles
        
        # CRITICAL: Configure ahoy to play multiple roles across protocols
        # This remaps all specified roles to the "ahoy" agent in the systems dict
        # Must be done BEFORE checking which agents are needed
        if roles_list:
            log_debug(f"Configuring ahoy to play multiple roles: {roles_list}")
            from configuration import configure_ahoy_for_multiprotocol
            configure_ahoy_for_multiprotocol(roles_list)
        
        # Otherwise, determine which agent(s) are needed to play these roles
        agent_roles = {}  # agent_id -> list of (protocol, role) tuples
        
        for protocol_name, role_name in roles_list:
            protocol_config = systems.get(protocol_name)
            if not protocol_config:
                log_debug(f"ERROR: Protocol '{protocol_name}' not found in systems")
                return None, []
            
            # Find which agent plays this role
            protocol = protocol_config["protocol"]
            role_obj = protocol.roles.get(role_name)
            if not role_obj:
                log_debug(f"ERROR: Role '{role_name}' not found in protocol '{protocol_name}'")
                return None, []
            
            agent_identity = protocol_config["roles"].get(role_obj)
            if not agent_identity:
                log_debug(f"ERROR: No agent assigned to {protocol_name}:{role_name}")
                return None, []
            
            if agent_identity not in agent_roles:
                agent_roles[agent_identity] = []
            agent_roles[agent_identity].append((protocol_name, role_name))
        
        log_debug(f"Determined agent assignments: {agent_roles}")
        
        # Ahoy supports one agent identity at a time
        # That agent can play multiple roles across multiple protocols
        if len(agent_roles) > 1:
            agents_str = ", ".join(agent_roles.keys())
            log_debug(f"ERROR: Multiple different agents needed: {agents_str}. Ahoy supports one agent per instance.")
            log_debug(f"Note: One agent CAN play multiple roles. These are multiple different agents.")
            return None, []
        
        agent_identity = list(agent_roles.keys())[0]
        assigned_roles = agent_roles[agent_identity]
        
        log_debug(f"Agent identity: {agent_identity}")
        log_debug(f"Roles: {assigned_roles}")
        
        return agent_identity, assigned_roles
        
    except Exception as e:
        log_debug(f"Error reading protocol/role config: {e}")
        log_debug(f"Traceback: {traceback.format_exc()}")
        return None, []


def initialize_ahoy_from_globals():
    """
    Initialize ahoy adapter and decision handler.
    
    Call this when you've already set assigned_agent_identity and assigned_roles_list,
    but need to initialize the adapter and decision handler infrastructure.
    
    Used by demo scripts and other external integrations.
    """
    global adapter
    
    if not assigned_agent_identity or not assigned_roles_list:
        raise ValueError(f"assigned_agent_identity and assigned_roles_list must be set before calling initialize_ahoy_from_globals(). Got agent={assigned_agent_identity}, roles={assigned_roles_list}")
    
    log_debug(f"Initializing ahoy agent: {assigned_agent_identity}")
    log_debug(f"Roles: {assigned_roles_list}")
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # If no event loop exists, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Update the systems dict to map all ahoy's roles to "ahoy" agent
    from configuration import configure_ahoy_for_multiprotocol
    log_debug(f"Configuring systems dict for ahoy with roles: {assigned_roles_list}")
    configure_ahoy_for_multiprotocol(assigned_roles_list)
    
    # Initialize tracking systems
    _initialize_tracking_systems()
    
    # Create single adapter for this agent (handles all their roles)
    try:
        adapter, error = create_adapter_for_agent(assigned_agent_identity)
        
        if error:
            raise SystemExit(f"Failed to create adapter for {assigned_agent_identity}: {error}")
        
        log_debug(f"Adapter created successfully for agent: {assigned_agent_identity}")
    except Exception as e:
        log_debug(f"Error creating adapter: {e}")
        raise
    
    # Register enabled message handlers for all send messages across all roles
    _register_enabled_message_handlers()
    
    # Initialize protocol analysis (extract request-response mappings using LLM)
    try:
        _initialize_protocol_analysis(assigned_protocol, assigned_role)
    except Exception as e:
        log_debug(f"Warning: Protocol analysis failed (non-fatal): {e}")
    
    # Write claimed roles to file so start script knows not to start these agents
    try:
        claimed_role_dir = Path(tempfile.gettempdir())
        claimed_role_file = claimed_role_dir / f"maf_claimed_role_{getpid()}.txt"
        roles_str = ",".join([f"{p}:{r}" for p, r in assigned_roles_list])
        claimed_role_file.write_text(roles_str)
        log_debug(f"Claimed roles written to temp file: {claimed_role_file}")
    except Exception as e:
        log_debug(f"Warning: Could not write claimed role file: {e}")
    
    # Reset agent notes for fresh run
    for protocol, role in assigned_roles_list:
        reset_agent_notes(role)
    reset_agent_notes(assigned_agent_identity)
    reset_agent_notes('Adapter')
    
    # Register LLM decision handler
    try:
        llm_decision_handler = loop.run_until_complete(_get_llm_decision_handler())
    except Exception as e:
        log_debug(f"Error getting LLM decision handler: {e}")
        raise
    
    # Register handler and start adapter
    adapter.decision()(llm_decision_handler)
    adapter.start(main())


if __name__ == "__main__":
    try:
        # Initialize tracking systems
        _initialize_tracking_systems()
        
        # Phase 1: Initialize protocol and roles from CHIPS config
        loop = asyncio.get_event_loop()
        agent_identity, roles_list = loop.run_until_complete(_initialize_protocol_and_role())
        
        if not agent_identity or not roles_list:
            raise SystemExit("Failed to determine agent identity and role(s)")
        
        log_debug(f"Agent assigned: {agent_identity}")
        log_debug(f"Roles: {roles_list}")
        
        # Set module-level globals
        assigned_agent_identity = agent_identity
        assigned_roles_list = roles_list
        assigned_protocol = roles_list[0][0]  # First protocol (for backward compat)
        assigned_role = roles_list[0][1]      # First role (for backward compat)
        
        # IMPORTANT: Update the systems dict to map all ahoy's roles to "ahoy" agent
        # This allows the Adapter to discover all roles assigned to ahoy
        from configuration import configure_ahoy_for_multiprotocol
        log_debug(f"Configuring systems dict for ahoy with roles: {roles_list}")
        configure_ahoy_for_multiprotocol(roles_list)
        
        # Phase 2: Create single adapter for this agent
        # The adapter automatically handles all roles the agent plays across all protocols
        from lib.dynamic_adapter_manager import create_adapter_for_agent
        adapter, error = create_adapter_for_agent(agent_identity)
        
        if error:
            raise SystemExit(f"Failed to create adapter for {agent_identity}: {error}")
        
        log_debug(f"Adapter created successfully for agent: {agent_identity}")
        if len(roles_list) > 1:
            roles_str = ", ".join([f"{r}({p})" for p, r in roles_list])
            log_debug(f"Adapter will handle multiple roles: {roles_str}")
        
        # Register enabled message handlers for all send messages across all roles
        _register_enabled_message_handlers()
        
        # Initialize protocol analysis for each role (extract request-response mappings using LLM)
        log_debug(f"Initializing protocol analysis for {len(assigned_roles_list)} role(s)...")
        for protocol, role in assigned_roles_list:
            _initialize_protocol_analysis(protocol, role)
        
        # Write claimed roles to file so start script knows not to start these agents
        try:
            claimed_role_dir = Path(tempfile.gettempdir())
            claimed_role_file = claimed_role_dir / f"maf_claimed_role_{getpid()}.txt"
            roles_str = ",".join([f"{p}:{r}" for p, r in roles_list])
            claimed_role_file.write_text(roles_str)
            log_debug(f"Claimed roles written to temp file: {claimed_role_file}")
        except Exception as e:
            log_debug(f"Warning: Could not write claimed role file: {e}")
        
        # Reset agent notes for fresh run
        for protocol, role in roles_list:
            reset_agent_notes(role)
        reset_agent_notes(agent_identity)
        reset_agent_notes('Adapter')
        
        # Phase 3: Register LLM decision handler
        log_debug("Phase 3: Registering LLM decision handler")
        llm_decision_handler = loop.run_until_complete(_get_llm_decision_handler())
        
        # Register handler and start adapter
        adapter.decision()(llm_decision_handler)
        adapter.start(main())
        
    except KeyboardInterrupt:
        log_debug("Interrupted by user")
    except SystemExit as e:
        log_debug(f"System exit: {e}")
        
        exit_msg = str(e)
        if "Goal achieved" in exit_msg or "completed" in exit_msg.lower():
            print(f"\n{'='*70}")
            print(f"✅ ROLES COMPLETED!")
            print(f"{'='*70}")
            if assigned_roles_list:
                roles_str = ", ".join([f"{r} in {p}" for p, r in assigned_roles_list])
                print(f"Completed: {roles_str}")
            print(f"{'='*70}\n")
        
    except Exception as e:
        log_debug(f"Error occurred: {str(e)}")
        log_debug(f"Full traceback:\n{traceback.format_exc()}")
        print(f"Error: {e}")
    finally:
        log_debug(f"Logs written to: {log_filename}")
        _cleanup_logging()
