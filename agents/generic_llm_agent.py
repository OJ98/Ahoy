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
)
from lib.llm_client import initialize_llm_tracker, get_llm_tracker
from lib.agent_notes import get_agent_notes, reset_agent_notes
from lib.protocol_discovery import (
    get_all_protocols,
    validate_protocol_and_role,
    get_protocol_summary_for_llm,
)
from lib.protocol_completion_detector import is_completion_message
from lib.dynamic_adapter_manager import create_adapter_for_role, get_color_for_protocol_role

# Set global timeout
TIMEOUT = 30.0

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

# Initialize logging system
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = str(LOG_DIR / f"generic_agent_debug_{timestamp}.log")

debug_logger, console_logger = setup_logging(log_filename, mode='a')

# Adapter will be created dynamically after protocol/role decision
adapter = None
assigned_protocol = None
assigned_role = None

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
    Main entry point: Waits for protocol to complete.
    """
    try:
        log_debug(f"Generic agent ready for {assigned_protocol}.{assigned_role}. Waiting for protocol events...")
        
        # Keep the adapter running indefinitely
        await shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH))
    
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
        log_debug(f"DEBUG: llm_decision called for {assigned_protocol}.{assigned_role}")
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
        
        # Call LLM to decide on available messages
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
            # If LLM deferred choice for tools, we need to retry the decision
            # This allows the LLM to make a message choice on the next call with tool results available
            # Return None to skip this event, and adapter will check again
            return None

        log_debug(f"DEBUG: Sending message: {instance}")
        
        # Check if this message completes the role
        if hasattr(instance, 'schema') and hasattr(instance.schema, 'name'):
            msg_type = instance.schema.name
            if is_completion_message(assigned_protocol, assigned_role, msg_type):
                _handle_role_completion(instance)
        
        return instance
    
    return llm_decision


def _initialize_tracking_systems():
    """Initialize LLM call tracker."""
    initialize_llm_tracker(max_calls=20, max_duration_seconds=180.0)
    log_debug("LLM tracker initialized: max 20 calls or 3 minutes")


def _cleanup_logging():
    """Close all logging handlers."""
    for handler in debug_logger.handlers:
        handler.close()
    for handler in console_logger.handlers:
        handler.close()


async def _initialize_protocol_and_role():
    """
    First phase: LLM decides which protocol and role to use via a single API call.
    
    Returns:
        tuple: (protocol_name, role_name) or (None, None) on failure
    """
    global assigned_protocol, assigned_role, adapter
    
    log_debug("INITIALIZATION PHASE: LLM will choose protocol and role")
    
    # Get protocol context for LLM
    protocol_summary = get_protocol_summary_for_llm()
    log_debug(f"Available protocols:\n{protocol_summary}")
    
    # Load user input for context
    input_file = PROJECT_ROOT / "input.txt"
    user_input = ""
    if input_file.exists():
        user_input = input_file.read_text()
        log_debug(f"User input: {user_input}")
    
    try:
        # Create prompt for LLM to determine protocol and role
        protocol_choices_str = protocol_summary.replace("\n", "\n  ")
        
        prompt = f"""You are a protocol selection assistant. Based on the user's goal, determine which protocol and role they should participate in.

Available Protocols:
{protocol_choices_str}

User's Goal:
{user_input}

Respond with ONLY the protocol and role in this format:
PROTOCOL: <ProtocolName>
ROLE: <RoleName>

Be concise and direct. Do not explain your reasoning."""
        
        log_debug(f"Sending protocol/role detection prompt to LLM")
        
        # Make a single LLM call to determine protocol and role
        response = await llm_client.complete(prompt, max_tokens=100)
        log_debug(f"LLM response for protocol/role: {response}")
        
        # Parse the response to extract protocol and role
        lines = response.strip().split('\n')
        protocol_name = None
        role_name = None
        
        for line in lines:
            if line.startswith('PROTOCOL:'):
                protocol_name = line.replace('PROTOCOL:', '').strip()
            elif line.startswith('ROLE:'):
                role_name = line.replace('ROLE:', '').strip()
        
        # Validate that the protocol and role exist
        if protocol_name and role_name:
            is_valid, error_msg = validate_protocol_and_role(protocol_name, role_name)
            if is_valid:
                log_debug(f"LLM selected: {protocol_name} - {role_name}")
                return protocol_name, role_name
            else:
                log_debug(f"LLM selection invalid: {error_msg}")
        
        # Fallback if LLM response couldn't be parsed or was invalid
        log_debug("Could not parse LLM response, defaulting to Purchase.Buyer")
        return "Purchase", "Buyer"
        
    except Exception as e:
        log_debug(f"Error during protocol/role initialization: {e}")
        log_debug(f"Traceback: {traceback.format_exc()}")
        return None, None


if __name__ == "__main__":
    try:
        # Initialize tracking systems
        _initialize_tracking_systems()
        
        # Phase 1: Initialize protocol and role
        # Run async initialization
        loop = asyncio.get_event_loop()
        assigned_protocol, assigned_role = loop.run_until_complete(_initialize_protocol_and_role())
        
        if not assigned_protocol or not assigned_role:
            raise SystemExit("Failed to determine protocol and role")
        
        log_debug(f"Agent assigned to: {assigned_protocol}.{assigned_role}")
        
        # Phase 2: Create adapter for the assigned protocol/role
        color_idx = get_color_for_protocol_role(assigned_protocol, assigned_role)
        adapter, error = create_adapter_for_role(assigned_protocol, assigned_role, color_idx)
        
        if error:
            raise SystemExit(f"Failed to create adapter: {error}")
        
        log_debug(f"Adapter created successfully for {assigned_protocol}.{assigned_role}")
        
        # Write claimed role to file so start script knows not to start this agent
        try:
            claimed_role_dir = Path(tempfile.gettempdir())
            claimed_role_file = claimed_role_dir / f"maf_claimed_role_{getpid()}.txt"
            claimed_role_file.write_text(f"{assigned_protocol}:{assigned_role}")
            log_debug(f"Claimed role written to temp file: {claimed_role_file}")
        except Exception as e:
            log_debug(f"Warning: Could not write claimed role file: {e}")
        
        # Reset agent notes for fresh run
        reset_agent_notes(assigned_role)
        reset_agent_notes('Adapter')
        
        # Phase 3: Register the LLM decision handler with the adapter
        # We need to dynamically decorate the handler
        llm_decision_handler = loop.run_until_complete(_get_llm_decision_handler())
        adapter.decision()(llm_decision_handler)
        
        # Phase 4: Start the adapter and main loop
        adapter.start(main())
        
    except KeyboardInterrupt:
        log_debug("Interrupted by user")
    except SystemExit as e:
        log_debug(f"System exit: {e}")
        
        exit_msg = str(e)
        if "Goal achieved" in exit_msg:
            print(f"\n{'='*70}")
            print(f"✅ ROLE COMPLETED!")
            print(f"{'='*70}")
            if assigned_protocol and assigned_role:
                print(f"{assigned_role} in {assigned_protocol} protocol completed successfully")
            print(f"{'='*70}\n")
        
    except Exception as e:
        log_debug(f"Error occurred: {str(e)}")
        log_debug(f"Full traceback:\n{traceback.format_exc()}")
        print(f"Error: {e}")
    finally:
        log_debug(f"Logs written to: {log_filename}")
        _cleanup_logging()
