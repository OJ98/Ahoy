#!/usr/bin/env python3

import asyncio
import json
import logging
import traceback
from datetime import datetime

from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
import bspl.adapter.receiver as _recv

# Import the protocol
import Purchase
from Purchase import Buyer, rfq, quote, accept, reject, deliver, completed

# Import the helper modules
from lib import (
    AnthropicLLMClient,
    choose_and_bind,
    UserInterface,
    setup_logging,
    log_debug,
    print_event_debug,
    print_enabled_store_debug,
    gather_requirements_from_user,
    shutdown_watcher,
)
from lib.llm_client import initialize_llm_tracker, get_llm_tracker
from lib.agent_notes import get_agent_notes
from lib.agent_notes import get_agent_notes_tracker

# Set global timeout
TIMEOUT = 30.0

# Initialize logging system
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"./logs/buyer_debug_{timestamp}.log"

debug_logger, console_logger = setup_logging(log_filename)

# Instantiate the adapter for the Buyer role
adapter = Adapter(Buyer, systems, agents, color=COLORS[0])
_recv.adapter = adapter

# Suppress adapter's internal logging to console
adapter_logger = logging.getLogger("bspl")
adapter_logger.setLevel(logging.CRITICAL)
adapter_logger.propagate = False

# Instantiate the user interface
ui = UserInterface()

# Instantiate the LLM client
llm_client = AnthropicLLMClient()

# Reset agent notes at startup - fresh notes for each run
from lib.agent_notes import reset_agent_notes
reset_agent_notes('Buyer')
reset_agent_notes('Adapter')

# Initialize the agent notes system for tracking decisions and actions
notes = get_agent_notes('Buyer')

# Global counters for transaction statistics (passed to display functions)
deliveries = 0
rejections = 0
accepted_deals = 0


async def initialize_buyer_with_llm():
    """
    Initialize the Buyer agent by gathering system requirements from user.
    This caches the system prompt for use in llm_decision handler.
    
    Returns:
        tuple: (role, system_prompt) or (None, None) on error
    """
    log_debug("Starting Buyer agent initialization...")
    log_debug("Gathering initial system requirements for Buyer role...")
    
    # Gather system requirements on startup
    inferred_role, system_prompt = await gather_requirements_from_user(
        llm_client,
        available_roles=["Buyer"],
        context="Purchase Protocol - Buyer Role",
        timeout=TIMEOUT,
        ui_callback=ui,
        logger_callback=log_debug
    )
    
    if not system_prompt:
        log_debug("Failed to gather system requirements")
        return None, None
    
    # Cache the system prompt for all future LLM calls
    from lib.llm_client import _SYSTEM_PROMPT_CACHE
    import lib.llm_client as llm_module
    llm_module._SYSTEM_PROMPT_CACHE = system_prompt
    log_debug(f"System prompt cached globally for future LLM calls")
    
    log_debug(f"Buyer initialization complete. Role: {inferred_role}")
    log_debug(f"System prompt established:\n{system_prompt}")
    
    return inferred_role, system_prompt


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
    
    Used both before and after LLM calls to enforce resource limits.
    
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


def _get_param(obj, param_name):
    """
    Extract parameter value from either Message or Partial object.
    Tries multiple access patterns: bindings, dict key, attribute.
    
    Args:
        obj: Message or Partial object
        param_name: Name of parameter to extract
    
    Returns:
        Parameter value or None if not found
    """
    # Try accessing via bindings dict (Partial objects)
    if hasattr(obj, 'bindings') and obj.bindings:
        return obj.bindings.get(param_name)
    
    # Try accessing as dict key
    try:
        return obj[param_name]
    except (TypeError, KeyError):
        pass
    
    # Try accessing as attribute
    try:
        return getattr(obj, param_name, None)
    except AttributeError:
        pass
    
    return None


def _track_message_note(msg_type, instance, llm_call_num):
    """
    Track important protocol messages in agent notes system.
    Records message type, parameters, and LLM call count for analysis.
    
    Args:
        msg_type: Type of message (e.g., 'rfq', 'quote', 'accept', etc.)
        instance: The message instance with bindings
        llm_call_num: Current LLM call number for tracking
    """
    if not notes:
        return
    
    # Track RFQ messages
    if msg_type == 'rfq':
        rfq_id = _get_param(instance, 'ID')
        item = _get_param(instance, 'item')
        log_debug(f"[SENT] RFQ: ID={rfq_id}, item={item}")
    
    # Track quote responses
    elif msg_type == 'quote':
        rfq_id = _get_param(instance, 'ID')
        price = _get_param(instance, 'price')
        log_debug(f"[RECEIVED] Quote: ID={rfq_id}, price=${price}")
    
    # Track accept decisions
    elif msg_type == 'accept':
        transaction_id = _get_param(instance, 'ID')
        item = _get_param(instance, 'item')
        price = _get_param(instance, 'price')
        log_debug(f"[DECISION] Accept: ID={transaction_id}, item={item}, price=${price}")
    
    # Track reject decisions
    elif msg_type == 'reject':
        transaction_id = _get_param(instance, 'ID')
        item = _get_param(instance, 'item')
        price = _get_param(instance, 'price')
        outcome = _get_param(instance, 'outcome')
        log_debug(f"[DECISION] Reject: ID={transaction_id}, reason={outcome}")
    
    # Track delivery confirmations
    elif msg_type == 'deliver':
        transaction_id = _get_param(instance, 'ID')
        item = _get_param(instance, 'item')
        outcome = _get_param(instance, 'outcome')
        log_debug(f"[DELIVERY] ID={transaction_id}, outcome={outcome}")
    
    # Track completion message
    elif msg_type == 'completed':
        log_debug(f"[GOAL ACHIEVED] LLM sent completion signal: {instance}")


def _handle_transaction_completion(instance):
    """
    Handle successful transaction completion by creating stop signal.
    
    Args:
        instance: The completed message instance
    
    Raises:
        SystemExit: Always raises to signal completion
    """
    try:
        with open(".stop_signal", "w") as f:
            f.write("transaction_complete")
        log_debug("Stop signal created - all agents will shut down")
    except Exception as e:
        log_debug(f"Error creating stop signal: {e}")
    
    raise SystemExit(f"✅ Goal achieved: LLM marked transaction complete. {instance}")


async def main():
    """
    Main entry point: Waits for protocol to complete.
    
    System prompt must be cached before this runs, so that
    the llm_decision handler has it available immediately.
    """
    try:
        log_debug("Buyer agent ready. Waiting for protocol events...")
        
        # Keep the adapter running indefinitely
        # The llm_decision handler will be triggered by adapter events
        await shutdown_watcher(adapter)
    
    except Exception as e:
        log_debug(f"Error in main: {e}")
        ui.error_occurred(str(e))
        raise


@adapter.decision()
async def llm_decision(enabled_store, event):
    """
    LLM decision handler triggered by adapter on ANY protocol state change.
    This includes InitEvent at startup and subsequent message observations.
    System prompt is cached from initialization.
    
    Coordinates validation, LLM calls, message tracking, and threshold monitoring.
    """

    log_debug(f"DEBUG: llm_decision called")
    log_debug(f"  - enabled_store type: {type(enabled_store)}")
    log_debug(f"  - event type: {type(event)}")
    
    # Fallback requirement callback (system prompt should be cached)
    async def fallback_callback(roles):
        return "Buyer", "You are a buyer agent. Make prudent purchasing decisions."
    
    # Log event details
    print_event_debug(event)
    
    # Validate enabled_store and retrieve messages
    is_valid, messages = _validate_enabled_store(enabled_store)
    if not is_valid:
        return None
    
    log_debug("LLM decision invoked, enabled messages available.")
    print_enabled_store_debug(enabled_store)
    
    # Check threshold before making LLM call
    should_continue, reason = _check_threshold()
    if not should_continue:
        raise SystemExit(f"Graceful termination: {reason}")
    
    # Call LLM to decide on available messages
    log_debug("Consulting LLM for decision...")
    instance = await choose_and_bind(
        adapter=adapter,
        enabled_store=enabled_store,
        event=event,
        client=llm_client,
        timeout=TIMEOUT,
        logger_callback=log_debug,
        requirement_callback=fallback_callback
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
        return None

    log_debug(f"DEBUG: Sending message: {instance}")
    
    # Track important messages using agent notes
    if hasattr(instance, 'schema') and hasattr(instance.schema, 'name'):
        msg_type = instance.schema.name
        tracker = get_llm_tracker()
        llm_call_num = tracker.call_count if tracker else 0
        
        # Track different message types
        _track_message_note(msg_type, instance, llm_call_num)
        
        # Handle transaction completion
        if msg_type == 'completed':
            _handle_transaction_completion(instance)
    
    return instance


def _initialize_tracking_systems():
    """Initialize LLM call tracker and agent notes tracker."""
    # Initialize the LLM call tracker with thresholds: 20 calls or 3 minutes
    initialize_llm_tracker(max_calls=20, max_duration_seconds=180.0)
    log_debug("LLM tracker initialized: max 20 calls or 3 minutes")
    
    # Initialize agent notes tracker for general-purpose note tracking
    get_agent_notes_tracker('Buyer')
    log_debug("Agent notes tracker initialized with JSON file tracking")


def _display_transaction_summary(rejections_count, accepted_count, delivered_count):
    """Display final transaction summary statistics."""
    total = rejections_count + accepted_count + delivered_count
    if total > 0:
        ui.transaction_complete(total, rejections_count, accepted_count)
        log_debug(f"[FINAL] Transactions: Total={total}, Rejected={rejections_count}, Accepted={accepted_count}, Delivered={delivered_count}")
    else:
        ui.info("⏸", "No transactions processed")


def _export_agent_notes():
    """Export agent notes summary to file."""
    agent_notes = get_agent_notes('Buyer')
    if agent_notes:
        summary = agent_notes.get_summary()
        agent_notes.export(f"./logs/buyer_notes_{timestamp}.json")
        log_debug(f"\n[AGENT NOTES SUMMARY]\n{json.dumps(summary, indent=2)}")
        ui.info("📝", f"Agent notes exported: logs/buyer_notes_{timestamp}.json")


def _cleanup_logging():
    """Close all logging handlers."""
    for handler in debug_logger.handlers:
        handler.close()
    for handler in console_logger.handlers:
        handler.close()


if __name__ == "__main__":
    try:
        # Initialize tracking and monitoring systems
        _initialize_tracking_systems()
        
        # Initialize system prompt BEFORE starting the adapter
        # This ensures it's cached before the first decision event
        import asyncio as _asyncio
        role, system_prompt = _asyncio.run(initialize_buyer_with_llm())
        
        if not role:
            ui.error_occurred("Failed to initialize buyer")
        else:
            # Now start the adapter with the cached system prompt
            adapter.start(main())
            _display_transaction_summary(rejections, accepted_deals, deliveries)
    except KeyboardInterrupt:
        ui.interrupted()
    except SystemExit as e:
        # Handle graceful termination due to threshold or successful completion
        log_debug(f"System exit: {e}")
        ui.divider()
        
        # Check if this is a successful completion
        exit_msg = str(e)
        if "Goal achieved" in exit_msg or "successful" in exit_msg.lower():
            print(f"\n{'='*70}")
            print(f"✅ TRANSACTION COMPLETE!")
            print(f"{'='*70}")
            print(f"All agents are shutting down gracefully...")
            print(f"{'='*70}\n")
        
        # Show final statistics and export notes
        _display_transaction_summary(rejections, accepted_deals, deliveries)
        _export_agent_notes()
    except Exception as e:
        ui.error_occurred(str(e))
        log_debug(f"Full traceback:\n{traceback.format_exc()}")
    finally:
        ui.show_log_location(log_filename)
        _cleanup_logging()
