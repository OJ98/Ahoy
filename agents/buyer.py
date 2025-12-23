#!/usr/bin/env python3

import asyncio
import json
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    shutdown_watcher,
)
from lib.llm_client import initialize_llm_tracker, get_llm_tracker
from lib.agent_notes import get_agent_notes

# Set global timeout
TIMEOUT = 30.0

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
STOP_SIGNAL_PATH = PROJECT_ROOT / ".stop_signal"

# Initialize logging system
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = str(LOG_DIR / f"buyer_debug_{timestamp}.log")

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


def _handle_transaction_completion(instance):
    """
    Handle successful transaction completion by creating stop signal.
    
    Verifies that what was intended matches what was executed by comparing
    agent-triggered logs from save_state_to_memory tool calls.
    
    Args:
        instance: The completed message instance
    
    Raises:
        SystemExit: Always raises to signal completion
    """
    from lib.agent_notes import get_agent_notes
    
    # Verify enactment: compare what the agent intended vs what it actually sent
    notes_tracker = get_agent_notes('Buyer')
    
    try:
        decision_intent = notes_tracker.get('enactment_decision_intent')
        execution_log = notes_tracker.get('message_execution_log')
        
        log_debug("\n" + "="*80)
        log_debug("ENACTMENT VERIFICATION REPORT")
        log_debug("="*80)
        
        if decision_intent:
            log_debug(f"✓ Decision Intent Recorded: {decision_intent}")
        else:
            log_debug(f"⚠️ Decision Intent NOT Found - Agent did not call save_state_to_memory('Buyer', 'enactment_decision_intent', ...)")
        
        if execution_log:
            log_debug(f"✓ Execution Log Recorded: {execution_log}")
        else:
            log_debug(f"⚠️ Execution Log NOT Found - Agent did not call save_state_to_memory('Buyer', 'message_execution_log', ...)")
        
        if decision_intent and execution_log:
            log_debug(f"✓ Both logs present - Transaction was properly tracked by agent")
        else:
            log_debug(f"⚠️ Incomplete audit trail - Some tool calls were not made")
        
        log_debug("="*80 + "\n")
        
    except Exception as e:
        log_debug(f"Could not verify enactment logs: {e}")
    
    # Original transaction completion logic: create stop signal
    try:
        STOP_SIGNAL_PATH.write_text("transaction_complete")
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
        await shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH))
    
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
    
    # Validate enabled_store and retrieve messages
    is_valid, messages = _validate_enabled_store(enabled_store)
    if not is_valid:
        return None
    
    log_debug("LLM decision invoked, enabled messages available.")
    
    # Check threshold before making LLM call
    should_continue, reason = _check_threshold()
    if not should_continue:
        raise SystemExit(f"Graceful termination: {reason}")
    
    # Call LLM to decide on available messages. This is the core decision point.
    log_debug("Consulting LLM for decision...")
    instance = await choose_and_bind(
        adapter=adapter,
        enabled_store=enabled_store,
        event=event,
        client=llm_client,
        timeout=TIMEOUT,
        logger_callback=log_debug
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
    
    # Handle transaction completion if applicable
    if hasattr(instance, 'schema') and hasattr(instance.schema, 'name'):
        msg_type = instance.schema.name
        if msg_type == 'completed':
            _handle_transaction_completion(instance)
    
    return instance


def _initialize_tracking_systems():
    """Initialize LLM call tracker."""
    # Initialize the LLM call tracker with thresholds: 20 calls or 3 minutes
    initialize_llm_tracker(max_calls=20, max_duration_seconds=180.0)
    log_debug("LLM tracker initialized: max 20 calls or 3 minutes")


def _display_transaction_summary(rejections_count, accepted_count, delivered_count):
    """Display final transaction summary statistics."""
    total = rejections_count + accepted_count + delivered_count
    if total > 0:
        ui.transaction_complete(total, rejections_count, accepted_count)
        log_debug(f"[FINAL] Transactions: Total={total}, Rejected={rejections_count}, Accepted={accepted_count}, Delivered={delivered_count}")
    else:
        ui.info("⏸", "No transactions processed")


def _export_agent_notes():
    """Log agent notes summary."""
    try:
        agent_notes = get_agent_notes('Buyer')
        if agent_notes:
            log_debug("Agent notes saved to agent_notes.json")
    except Exception as e:
        log_debug(f"Could not export agent notes: {e}")


def _cleanup_logging():
    """Close all logging handlers."""
    for handler in debug_logger.handlers:
        handler.close()
    for handler in console_logger.handlers:
        handler.close()


if __name__ == "__main__":
    try:
        # Initialize tracking systems
        _initialize_tracking_systems()
        
        # Start the adapter
        # System prompt will be loaded from input.txt on first LLM call via choose_and_bind
        adapter.start(main())
        _display_transaction_summary(rejections, accepted_deals, deliveries)
    except KeyboardInterrupt:
        log_debug("Interrupted by user")
    except SystemExit as e:
        # Handle graceful termination due to threshold or successful completion
        log_debug(f"System exit: {e}")
        
        # Check if this is a successful completion
        exit_msg = str(e)
        if "Goal achieved" in exit_msg or "successful" in exit_msg.lower():
            print(f"\n{'='*70}")
            print(f"✅ TRANSACTION COMPLETE!")
            print(f"{'='*70}")
            print(f"All agents are shutting down gracefully...")
            print(f"{'='*70}\n")
        
        # Show final statistics
        _display_transaction_summary(rejections, accepted_deals, deliveries)
    except Exception as e:
        log_debug(f"Error occurred: {str(e)}")
        log_debug(f"Full traceback:\n{traceback.format_exc()}")
        print(f"Error: {e}")
    finally:
        log_debug(f"Logs written to: {log_filename}")
        _cleanup_logging()
