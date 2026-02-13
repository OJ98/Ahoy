#!/usr/bin/env python3

import asyncio
import json
import logging
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path
from os import getpid
import os

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
    create_or_update_termination_condition,
    update_termination_condition_progress,
    get_termination_condition_summary,
    reset_termination_conditions,
)
from lib.llm_client import initialize_llm_tracker, get_llm_tracker
from lib.agent_notes import get_agent_notes, reset_agent_notes
from lib.protocol_completion_detector import (
    extract_completion_rule_from_protocol
)
from lib.dynamic_adapter_manager import create_adapter_for_role, create_adapter_for_agent, get_color_for_protocol_role
from lib.custom_event_handler import EventQueue

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
event_queue = None  # Custom event queue for external system integration (initialized at startup)

# Counter for consecutive LLM calls without new external events (to prevent infinite polling)
consecutive_empty_event_calls = 0
MAX_EMPTY_EVENT_CALLS = 5

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
            # Unpack with protocol and role info if available (new format: 5 values)
            # or fall back to just message/direction/count if not (old format: 3 values)
            if len(rule) >= 5:
                msg_type, direction, count, rule_protocol, rule_role = rule[:5]
                log_debug(f"Successfully extracted completion rule for {rule_protocol}/{rule_role}: {msg_type} {direction} x{count}")
            else:
                msg_type, direction, count = rule[:3]
                log_debug(f"Successfully extracted completion rule for {protocol_name}/{role_name}: {msg_type} {direction} x{count}")
        else:
            raise RuntimeError(f"Failed to extract completion rule for {protocol_name}/{role_name} from LLM")
    except Exception as e:
        log_debug(f"Error during protocol analysis for {protocol_name}/{role_name}: {e}")
        raise


def _is_cached_completion_message(protocol_name: str, role_name: str, message_name: str, direction: str = None) -> tuple:
    """
    Check if a message indicates role completion based on cached LLM extraction.
    Uses the protocol_completion_rules cache populated by _initialize_protocol_analysis.
    
    Args:
        protocol_name: Name of protocol
        role_name: Name of role
        message_name: Name of message being checked
        direction: Optional direction filter ("send" or "receive")
    
    Returns:
        Tuple of (matches: bool, required_count: int)
        - matches: True if message type and direction match the rule
        - required_count: The count required from the rule (for multirole message validation)
    
    Raises:
        RuntimeError: If no cached rule exists (should not happen if _initialize_protocol_analysis was called)
    """
    rule = protocol_completion_rules.get((protocol_name, role_name))
    if rule is None:
        raise RuntimeError(f"No cached completion rule for {protocol_name}/{role_name}. _initialize_protocol_analysis must be called first.")
    
    # Unpack rule
    if len(rule) >= 5:
        msg_type, rule_direction, count, _, _ = rule[:5]
    else:
        msg_type, rule_direction, count = rule[:3]
    
    # Check message name matches
    if message_name.lower() != msg_type.lower():
        return False, count
    
    # Check direction if specified
    if direction is not None and direction.lower() != rule_direction.lower():
        return False, count
    
    return True, count


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
    Handle role completion by creating stop signal with role information.
    
    Args:
        instance: The completed message instance
    
    Raises:
        SystemExit: Always raises to signal completion
    """
    try:
        import json
        from datetime import datetime
        
        # Record which roles are terminating
        completed_roles_to_record = []
        for protocol, role in assigned_roles_list:
            completed_roles_to_record.append(f"{protocol}:{role}")
        
        termination_record = {
            "status": "transaction_complete",
            "completed_roles": completed_roles_to_record,
            "agent": assigned_agent_identity,
            "timestamp": datetime.now().isoformat()
        }
        
        STOP_SIGNAL_PATH.write_text(json.dumps(termination_record, indent=2))
        log_debug(f"Stop signal created with roles: {completed_roles_to_record}")
    except Exception as e:
        log_debug(f"Error creating stop signal: {e}")
    
    # Clear the event queue as part of cleanup
    try:
        from lib.event_injector import drain_event_queue
        cleared_count = drain_event_queue()
        if cleared_count > 0:
            log_debug(f"DEBUG: Cleared {cleared_count} event(s) from queue during completion cleanup")
    except Exception as e:
        log_debug(f"WARNING: Failed to clear event queue during cleanup: {e}")
    
    raise SystemExit(f"✅ Goal achieved: All roles completed for {assigned_agent_identity}. {instance}")


def _check_all_roles_completion(sent_message_instance):
    """
    For multirole agents, check if all assigned roles have completed.
    
    Checks both sent and received completion messages for each role:
    - A role completes when it SENDS its completion message, OR
    - A role completes when it RECEIVES its completion message
    
    Reuses the same completion message detection logic as single-role,
    but applies it to each role in assigned_roles_list.
    
    Args:
        sent_message_instance: The message instance just sent (or None if checking only history)
    
    Returns:
        bool: True if ALL roles have had their completion message sent/received, False otherwise
    """
    if len(assigned_roles_list) <= 1:
        # Single-role case handled directly in caller
        return True
    
    try:
        from lib.agent_notes import get_agent_notes
        from lib.state_manager import extract_social_state
        
        # Get current completion tracking state from agent notes
        agent_notes_obj = get_agent_notes(assigned_agent_identity)
        completed_roles = agent_notes_obj.get("completed_roles", [])
        
        log_debug(f"DEBUG: Checking multirole completion. Currently completed: {completed_roles}")
        
        # Get message history for checking received completions
        social_state = extract_social_state(adapter)
        # Note: extract_social_state stores all messages at result["all_messages"] (top level),
        # not in each system entry. Use the aggregated list directly.
        all_messages = social_state.get("all_messages", [])
        
        log_debug(f"DEBUG: Total messages in history: {len(all_messages)}")
        
        # Check each role to see if we've now completed it
        all_completed = True
        for protocol, role in assigned_roles_list:
            role_key = f"{protocol}:{role}"
            
            # If already marked complete, skip detailed check
            if role_key in completed_roles:
                log_debug(f"DEBUG:   {role_key} already marked complete")
                continue
            
            role_name_str = str(role)
            
            # Check 1: Did this role SEND a completion message?
            # COUNT all sent completion messages (must reach required_count)
            sent_count = 0
            send_msg_matches_found = False
            send_required_count = 1
            
            if hasattr(sent_message_instance, 'schema') and hasattr(sent_message_instance.schema, 'name'):
                msg_type = sent_message_instance.schema.name
                msg_matches, rule_count = _is_cached_completion_message(protocol, role, msg_type, direction="send")
                if msg_matches:
                    send_msg_matches_found = True
                    send_required_count = rule_count  # Get the required count from rule
                    sent_count = 1  # Count the message being sent RIGHT NOW (before it's added to history)
            
            # If we found a matching send rule, count all previously sent instances in message history
            if send_msg_matches_found:
                for msg in all_messages:
                    msg_matches, _ = _is_cached_completion_message(protocol, role, msg.get("schema_name", ""), direction="send")
                    if msg_matches:
                        sender = msg.get("sender")
                        # Count only messages sent BY this role (already in history)
                        if sender and role_name_str.lower() == str(sender).lower():
                            sent_count += 1
                
                log_debug(f"DEBUG:   {role_key} sent {sent_count}/{send_required_count} completion messages (including current)")
                
                if sent_count >= send_required_count:
                    log_debug(f"DEBUG:   {role_key} completion threshold reached by sending!")
                    completed_roles.append(role_key)
                    agent_notes_obj.save("completed_roles", completed_roles)
                    continue
            
            # Check 2: Did this role RECEIVE a completion message?
            # COUNT all received completion messages (must reach required_count)
            received_count = 0
            msg_matches_found = False
            required_count = 1  # Default if no rule found
            
            for msg in all_messages:
                msg_matches, rule_count = _is_cached_completion_message(protocol, role, msg.get("schema_name", ""), direction="receive")
                if msg_matches:
                    msg_matches_found = True
                    required_count = rule_count  # Update with the actual required count from rule
                    sender = msg.get("sender")
                    recipients = msg.get('recipients', [])
                    # Count only messages actually received by this role (from someone else)
                    if (sender and str(sender).lower() != role_name_str.lower() and
                        role_name_str.lower() in [str(r).lower() for r in recipients]):
                        received_count += 1
            
            if msg_matches_found:
                log_debug(f"DEBUG:   {role_key} received {received_count}/{required_count} completion messages")
            else:
                log_debug(f"DEBUG:   {role_key} no completion messages received yet")
            
            role_completed = False
            if msg_matches_found and received_count >= required_count:
                log_debug(f"DEBUG:   {role_key} completion threshold reached by receiving!")
                role_completed = True
            
            if role_completed:
                completed_roles.append(role_key)
                agent_notes_obj.save("completed_roles", completed_roles)
            
            # Check if this role is now complete
            if role_key not in completed_roles:
                all_completed = False
                log_debug(f"DEBUG:   {role_key} still pending")
            else:
                log_debug(f"DEBUG:   {role_key} is complete")
        
        if all_completed:
            log_debug(f"\nDEBUG: ✓✓ ALL {len(assigned_roles_list)} ROLES COMPLETED")
            return True
        else:
            log_debug(f"\nDEBUG: Not all roles complete yet")
            return False
    
    except Exception as e:
        log_debug(f"Error checking multirole completion: {e}")
        import traceback
        log_debug(f"Traceback: {traceback.format_exc()}")
        return False


async def _monitor_event_queue():
    """
    Background task: Periodically monitor the event queue for new external events.
    This ensures that events injected by external systems are available to the LLM
    in its decision context, even if they arrive after initial protocol decisions.
    
    Also generates and updates termination conditions based on detected events.
    """
    try:
        from lib.event_injector import _load_event_queue_file, get_agent_event_queue
        
        last_event_count = 0
        
        while True:
            try:
                queue_file = get_agent_event_queue()
                if queue_file.exists():
                    queue_data = _load_event_queue_file()
                    current_event_count = len(queue_data.get("events", []))
                    
                    # Log when new events are detected
                    if current_event_count > last_event_count:
                        new_events = queue_data.get("events", [])[last_event_count:]
                        for evt in new_events:
                            event_msg = evt.get('message', 'Unknown')
                            event_meta = evt.get('metadata', {})
                            
                            log_debug(f"[EVENT_MONITOR] New external event detected: {event_msg}")
                            if event_meta:
                                for k, v in event_meta.items():
                                    log_debug(f"  └─ {k}: {v}")
                            
                            # Generate termination condition for this event
                            if assigned_protocol and protocol_completion_rules:
                                try:
                                    created = create_or_update_termination_condition(
                                        event_message=event_msg,
                                        event_metadata=event_meta,
                                        protocol_name=assigned_protocol,
                                        completion_rules=protocol_completion_rules,
                                        agent_identity=assigned_agent_identity
                                    )
                                    if created:
                                        log_debug(f"[EVENT_MONITOR] Termination condition created for event: {event_msg}")
                                        
                                        # Log condition summary
                                        try:
                                            summary = get_termination_condition_summary()
                                            log_debug(f"[EVENT_MONITOR] Active conditions: {summary['pending']} pending, {summary['completed']} completed")
                                        except Exception as e:
                                            log_debug(f"[EVENT_MONITOR] Could not retrieve condition summary: {e}")
                                    else:
                                        log_debug(f"[EVENT_MONITOR] Failed to create termination condition for event: {event_msg}")
                                except Exception as e:
                                    log_debug(f"[EVENT_MONITOR] Error generating termination condition: {e}")
                        
                        last_event_count = current_event_count
            
            except Exception as e:
                log_debug(f"[EVENT_MONITOR] Error monitoring queue: {e}")
            
            # Check for events every 100ms
            await asyncio.sleep(0.1)
    
    except Exception as e:
        log_debug(f"Error in event monitor task: {e}")


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
        
        # Start background event monitor task
        monitor_task = asyncio.create_task(_monitor_event_queue())
        
        try:
            # Keep the adapter running until protocol completes
            # The decision handler will be called on InitEvent to send initial messages if needed
            await shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH))
        finally:
            # Cancel the monitor task when shutdown watcher exits
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
    
    except SystemExit:
        raise  # Let completion signals propagate
    except Exception as e:
        log_debug(f"Error in main: {e}")
        ui.error_occurred(str(e))
        raise


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
        
        log_debug(f"DEBUG: llm_decision called for {assigned_protocol}.{assigned_role}")
        log_debug(f"  - enabled_store type: {type(enabled_store)}")
        log_debug(f"  - event type: {type(event)}")
        

        # For InitEvent with no enabled messages, still try to get LLM decision for initial sends
        is_init_event = isinstance(event, InitEvent)
        if is_init_event:
            log_debug(f"DEBUG: InitEvent detected for {assigned_protocol}.{assigned_role}")
        
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
        
        # Check for pending custom events from external systems (file-based queue)
        pending_event_context = ""
        pending_event_ids = []  # Track which event IDs are in this prompt
        has_external_events = False
        try:
            from lib.event_injector import _load_event_queue_file, get_agent_event_queue
            queue_file = get_agent_event_queue()
            log_debug(f"DEBUG: Event queue file path: {queue_file}")
            log_debug(f"DEBUG: Event queue file exists: {queue_file.exists()}")
            
            # Read the raw file to diagnose issues
            if queue_file.exists():
                try:
                    raw_content = queue_file.read_text()
                    log_debug(f"DEBUG: Raw queue file size: {len(raw_content)} bytes")
                    if len(raw_content) > 0:
                        log_debug(f"DEBUG: Raw queue file content (first 200 chars): {raw_content[:200]}")
                except Exception as e:
                    log_debug(f"DEBUG: Error reading raw file: {e}")
            
            file_events = _load_event_queue_file().get("events", [])
            log_debug(f"DEBUG: Loaded {len(file_events)} event(s) from queue file")
            
            if file_events:
                has_external_events = True
                pending_event_context = ""
                for event_idx, evt in enumerate(file_events, 1):
                    # Use timestamp as unique event ID since it's unique per event
                    event_id = evt.get('timestamp', str(evt))
                    pending_event_ids.append(event_id)  # Track this event
                    
                    # Format with clear event boundaries (protocol-agnostic):
                    # - Numbered headers ("Event #N:") clearly separate each event
                    # - Metadata grouped under "Metadata:" creates visual containment
                    # - Bullet points (•) clearly mark individual metadata items
                    # This prevents context bleeding between events when multiple events exist
                    pending_event_context += f"Event #{event_idx}:\n"
                    pending_event_context += f"  Message: {evt.get('message', 'Unknown event')}\n"
                    
                    if evt.get('metadata'):
                        pending_event_context += f"  Metadata:\n"
                        for k, v in evt['metadata'].items():
                            pending_event_context += f"    • {k}: {v}\n"
                    
                    # Add blank line between events for visual separation
                    if event_idx < len(file_events):
                        pending_event_context += "\n"
                
                log_debug(f"Pending custom events: {len(file_events)} event(s)")
                log_debug(f"DEBUG: Tracking event IDs: {pending_event_ids}")
                log_debug(f"DEBUG: Built pending_event_context (length={len(pending_event_context)}):")
                for line in pending_event_context.split('\n'):
                    if line.strip():
                        log_debug(f"  > {line}")
            else:
                log_debug(f"DEBUG: No events in queue file (queue is empty)")
        except Exception as e:
            log_debug(f"ERROR loading file-based events: {e}")
            import traceback
            log_debug(f"ERROR traceback: {traceback.format_exc()}")
        
        # Also check in-memory queue for backward compatibility
        if not pending_event_context and event_queue and event_queue.has_events():
            has_external_events = True
            pending_events = event_queue.peek_events()
            pending_event_context = ""
            for event_idx, evt in enumerate(pending_events, 1):
                pending_event_context += f"Event #{event_idx}:\n  Message: {evt}\n"
                if event_idx < len(pending_events):
                    pending_event_context += "\n"
            log_debug(f"Pending custom events: {len(pending_events)} event(s)")
        
        log_debug("LLM decision invoked, consulting LLM...")
        
        # DEBUG: Log pending events before LLM call
        if pending_event_context and len(pending_event_context.strip()) > 0:
            log_debug(f"DEBUG: About to call LLM with pending events (context length={len(pending_event_context)}, {len(pending_event_ids)} event IDs)")
        else:
            log_debug(f"DEBUG: About to call LLM with NO pending events")
        
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
            current_protocol=assigned_protocol,
            current_role=assigned_role,
            all_roles_list=assigned_roles_list,
            pending_event_context=pending_event_context,
            pending_event_ids=pending_event_ids  # Pass event IDs for tracking
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
            
            # Track consecutive empty LLM calls when no external events (to prevent infinite polling)
            global consecutive_empty_event_calls
            if not has_external_events and not is_init_event:
                consecutive_empty_event_calls += 1
                log_debug(f"DEBUG: No external events and LLM returned None. Empty call #{consecutive_empty_event_calls}/{MAX_EMPTY_EVENT_CALLS}")
                if consecutive_empty_event_calls >= MAX_EMPTY_EVENT_CALLS:
                    log_debug(f"DEBUG: Reached max consecutive empty calls ({MAX_EMPTY_EVENT_CALLS}), terminating to wait for external input")
                    raise SystemExit(f"Graceful termination: No external events after {MAX_EMPTY_EVENT_CALLS} consecutive LLM calls. Waiting for external input.")
            else:
                # Reset counter if we have external events or are in InitEvent
                if has_external_events:
                    consecutive_empty_event_calls = 0
                    log_debug(f"DEBUG: External events present, reset empty call counter")
            
            # If LLM deferred choice for tools, we need to retry the decision
            # This allows the LLM to make a message choice on the next call with tool results available
            # Return None to skip this event, and adapter will check again
            return None

        # Reset the empty call counter when LLM successfully makes a choice
        consecutive_empty_event_calls = 0
        log_debug(f"DEBUG: LLM made a choice, reset empty call counter")

        log_debug(f"DEBUG: Sending message: {instance}")
        
        # Update termination conditions when a message is sent
        # Use the same completion message checking logic as non-event code
        if instance is not None and hasattr(instance, 'schema') and hasattr(instance.schema, 'name'):
            try:
                msg_type = instance.schema.name
                
                # Check if this message completes any pending condition using the same logic as regular runs
                for (protocol, role) in assigned_roles_list:
                    # Use _is_cached_completion_message to check if this message completes the role
                    msg_matches, _ = _is_cached_completion_message(protocol, role, msg_type, direction="send")
                    if msg_matches:
                        log_debug(f"[TERMINATION] Message {msg_type} completes {protocol}:{role}")
                        
                        # This message completes the condition - find and update matching conditions
                        from lib.termination_condition_manager import _load_termination_conditions, get_termination_condition_file
                        
                        conditions_data = _load_termination_conditions()
                        
                        # Get message bindings to match transaction
                        # Messages support dict-like access: msg["field"]
                        msg_bindings = {}
                        try:
                            # Try to extract bound values from message instance
                            if hasattr(instance, 'payload'):
                                msg_bindings = dict(instance.payload)
                            else:
                                # Fallback: try to access as dict-like
                                for key in ['ID', 'item', 'price']:
                                    try:
                                        msg_bindings[key] = instance[key]
                                    except (KeyError, TypeError):
                                        pass
                        except Exception as e:
                            log_debug(f"[TERMINATION] Could not extract message bindings: {e}")
                        
                        log_debug(f"[TERMINATION] Message bindings: {msg_bindings}")
                        
                        for condition in conditions_data.get("conditions", []):
                            if condition.get("completion_status") == "pending" and \
                               condition.get("protocol", "").lower() == protocol.lower():
                                
                                # For event-based conditions, check if this message is for the same transaction
                                # by comparing key bindings (e.g., ID first, then item)
                                if condition.get("event_metadata"):
                                    # This is an event-based condition - match by ID or item
                                    event_metadata = condition.get("event_metadata", {})
                                    
                                    # Check if the message bindings match the event
                                    matches_event = False
                                    
                                    # Primary: check by ID
                                    if event_metadata.get("ID") and msg_bindings.get("ID"):
                                        if str(event_metadata.get("ID")) == str(msg_bindings.get("ID")):
                                            matches_event = True
                                            log_debug(f"[TERMINATION] Matched by ID: {msg_bindings.get('ID')}")
                                    
                                    # Secondary: check by item
                                    if not matches_event and event_metadata.get("item") and msg_bindings.get("item"):
                                        if event_metadata.get("item").lower() == str(msg_bindings.get("item")).lower():
                                            matches_event = True
                                            log_debug(f"[TERMINATION] Matched by item: {msg_bindings.get('item')}")
                                    
                                    if not matches_event:
                                        log_debug(f"[TERMINATION] Skipping {condition['id']} - transaction mismatch (event ID={event_metadata.get('ID')}, item={event_metadata.get('item')}, msg ID={msg_bindings.get('ID')}, item={msg_bindings.get('item')})")
                                        continue
                                
                                # Mark as complete
                                condition["completion_status"] = "complete"
                                condition["updated_at"] = datetime.now().isoformat()
                                
                                log_debug(f"[TERMINATION] Marked {condition['id']} as COMPLETE")
                                
                                # Save updated condition
                                condition_file = get_termination_condition_file()
                                with open(condition_file, 'w') as f:
                                    json.dump(conditions_data, f, indent=2)
                                
            except Exception as e:
                log_debug(f"[TERMINATION] Warning: {e}")
        
        # NOTE: Events are NOT cleared here. They persist in the queue so the LLM can continue
        # processing them across multiple decision cycles. Termination conditions handle cleanup
        # when events are actually completed by the protocol flow.
        
        # Update termination conditions based on current message history
        # This picks up both sent and received messages
        _update_termination_conditions_from_history()
        
        # Check if this message completes the role(s)
        if hasattr(instance, 'schema') and hasattr(instance.schema, 'name'):
            msg_type = instance.schema.name
            
            if len(assigned_roles_list) == 1:
                # Single-role: check if this role completes
                msg_matches, _ = _is_cached_completion_message(assigned_protocol, assigned_role, msg_type, direction="send")
                if msg_matches:
                    # Before exiting, verify all termination conditions are also complete
                    if _all_termination_conditions_complete():
                        _handle_role_completion(instance)
                    else:
                        log_debug(f"[COMPLETION] Protocol completion sent but termination conditions still pending")
            else:
                # Multi-role: check if all roles are now complete
                if _check_all_roles_completion(instance):
                    # Before exiting, verify all termination conditions are also complete
                    if _all_termination_conditions_complete():
                        _handle_role_completion(instance)
                    else:
                        log_debug(f"[COMPLETION] Multi-role completion reached but termination conditions still pending")
        
        return instance
    
    return llm_decision





def _update_termination_conditions_from_history():
    """
    Update termination conditions based on current message history.
    
    This scans all messages (both sent and received) and updates condition progress.
    Called after LLM decisions to account for received messages.
    """
    try:
        from lib.state_manager import extract_social_state
        from lib.termination_condition_manager import _load_termination_conditions, get_termination_condition_file
        
        # Get current message history
        social_state = extract_social_state(adapter)
        all_messages = social_state.get("all_messages", [])
        
        log_debug(f"[TERMINATION] Scanning {len(all_messages)} messages in history")
        
        conditions_data = _load_termination_conditions()
        
        for condition in conditions_data.get("conditions", []):
            if condition.get("completion_status") != "pending":
                continue  # Already complete or other status
                
            protocol = condition.get("protocol", "").lower()
            event_metadata = condition.get("event_metadata", {})
            
            if not event_metadata:
                continue  # Not an event condition
            
            # Get the item/ID from the event
            event_item = event_metadata.get("item", "").lower()
            event_id = event_metadata.get("ID", "")
            
            # Check message history for matching messages
            for msg in all_messages:
                msg_item = str(msg.get("item", "")).lower()
                msg_id = msg.get("ID", "")
                msg_type = msg.get("schema_name", "").lower()
                msg_role = str(msg.get("sender", "")).lower()
                
                # Check if message matches event transaction
                matches_transaction = False
                if event_id and msg_id == event_id:
                    matches_transaction = True
                elif event_item and msg_item == event_item:
                    matches_transaction = True
                
                if not matches_transaction:
                    continue
                
                # Check if this message completes the condition
                for (proto, role) in assigned_roles_list:
                    if proto.lower() == protocol:
                        msg_matches, _ = _is_cached_completion_message(proto, role, msg_type, direction=None)
                        if msg_matches:
                            log_debug(f"[TERMINATION] Found completion message {msg_type} for {condition['id']}")
                            condition["completion_status"] = "complete"
                            condition["updated_at"] = datetime.now().isoformat()
        
        # Save if any updates were made
        condition_file = get_termination_condition_file()
        with open(condition_file, 'w') as f:
            json.dump(conditions_data, f, indent=2)
            
    except Exception as e:
        log_debug(f"[TERMINATION] Warning scanning history: {e}")


def _all_termination_conditions_complete():
    """
    Check if all termination conditions are marked as complete.
    
    Returns:
        bool: True if all conditions are complete (or no event conditions exist), False otherwise
    """
    try:
        from lib.termination_condition_manager import _load_termination_conditions
        
        conditions_data = _load_termination_conditions()
        conditions = conditions_data.get("conditions", [])
        
        if not conditions:
            # No conditions = complete (no events to handle)
            return True
        
        # Check if ALL conditions are complete
        all_complete = all(c.get("completion_status") == "complete" for c in conditions)
        
        if all_complete:
            log_debug(f"[COMPLETION] ✓ All {len(conditions)} termination conditions are complete")
        else:
            pending_count = sum(1 for c in conditions if c.get("completion_status") != "complete")
            log_debug(f"[COMPLETION] ✗ {pending_count}/{len(conditions)} termination conditions still pending")
        
        return all_complete
    except Exception as e:
        log_debug(f"[COMPLETION] Warning checking termination conditions: {e}")
        return True  # If we can't check, assume complete to avoid blocking


def _initialize_tracking_systems():
    """Initialize LLM call tracker and reset termination conditions for fresh run."""
    initialize_llm_tracker(max_calls=50, max_duration_seconds=300.0)
    log_debug("LLM tracker initialized: max 20 calls or 3 minutes")
    
    # Reset termination conditions for fresh run
    reset_termination_conditions()
    log_debug("Termination conditions reset for new session")


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
    
    # Initialize file-based event queue IMMEDIATELY after adapter creation
    # This must happen before any LLM decisions are made
    try:
        from lib.event_injector import get_agent_event_queue
        queue_file = get_agent_event_queue()
        
        # Ensure parent directory exists
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create the file with empty events array
        if not queue_file.exists():
            with open(queue_file, 'w') as f:
                json.dump({"events": []}, f)
                f.flush()
        
        log_debug(f"Event queue file ready at: {queue_file}")
        log_debug(f"File exists and is readable: {queue_file.exists()}")
        
        # Brief pause to allow external systems time to post events before main loop
        log_debug("Pausing briefly to allow external systems to inject events...")
        time.sleep(1.0)  # Increased to 1 second for more reliable event posting
    except Exception as e:
        log_debug(f"Warning: Could not initialize event queue file (non-fatal): {e}")
        import traceback
        log_debug(f"Traceback: {traceback.format_exc()}")
    
    # Initialize custom event queue for external system integration
    global event_queue
    try:
        event_queue = EventQueue(protocol=assigned_protocol, role=assigned_role)
        log_debug(f"Event queue (in-memory) initialized for {assigned_protocol}.{assigned_role}")
    except Exception as e:
        log_debug(f"Warning: Could not initialize in-memory event queue (non-fatal): {e}")
    
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
        
        # Initialize event queue file at startup for external system integration
        # This allows event simulators to detect when the agent is ready
        try:
            from lib.event_injector import _load_event_queue_file, get_agent_event_queue
            queue_file = get_agent_event_queue()
            # Create an empty queue if it doesn't exist
            if not queue_file.exists():
                with open(queue_file, 'w') as f:
                    json.dump({"events": []}, f)
                log_debug(f"Initialized empty event queue at: {queue_file}")
        except Exception as e:
            log_debug(f"Warning: Could not initialize event queue file: {e}")
        
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
