#!/usr/bin/env python3
"""
Baseline 2: No Filtering (Exception-Driven Learning)

LLM sees ALL possible messages in the protocol (no enabled set filtering).
When invalid messages are attempted, kiko exceptions are caught and fed
back to the LLM as learning signals.

Strategy:
1. Patch choose_and_bind to expand enabled_store to all possible messages
2. Wrap adapter.send() to catch kiko exceptions
3. Feed exception feedback to LLM in next decision cycle
"""

import sys
from pathlib import Path

# Add parent directories to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set ablation mode environment variable
import os
os.environ["ABLATION_MODE"] = "baseline2_no_filtering"

# Import the variant utilities
sys.path.insert(0, str(Path(__file__).parent))
from utils_variant import (
    get_exception_tracker, 
    expand_enabled_to_all_messages,
    format_exception_feedback_for_prompt
)

# Monkey-patch the llm_client.choose_and_bind function to show all messages
# We'll do this after importing ahoy but before running main

# First, import the standard ahoy
import agents.ahoy as ahoy_module
import lib.llm_client as llm_client_module

# Store the original choose_and_bind
original_choose_and_bind = llm_client_module.choose_and_bind

async def choose_and_bind_no_filtering(
    adapter,
    enabled_store,
    event,
    client,
    *,
    timeout,
    logger_callback=None,
    agent_name="unknown",
    multi_protocol_states=None,
    current_protocol=None,
    current_role=None,
    all_roles_list=None,
    pending_event_context=None,
    pending_event_ids=None
):
    """
    Wrapped choose_and_bind that expands enabled_store to all possible messages.
    
    This is the key difference for baseline2: instead of filtering to enabled messages,
    show the LLM ALL messages and let it learn constraints via exceptions.
    """
    
    # Get exception feedback from previous decisions
    exception_tracker = get_exception_tracker()
    exception_feedback = exception_tracker.get_exception_feedback()
    
    # Augment pending_event_context with exception feedback
    if exception_feedback:
        if pending_event_context:
            pending_event_context = exception_feedback + "\n\n" + pending_event_context
        else:
            pending_event_context = exception_feedback
    
    # Call original choose_and_bind (which will be patched below to show all messages)
    result = await original_choose_and_bind(
        adapter=adapter,
        enabled_store=enabled_store,
        event=event,
        client=client,
        timeout=timeout,
        logger_callback=logger_callback,
        agent_name=agent_name,
        multi_protocol_states=multi_protocol_states,
        current_protocol=current_protocol,
        current_role=current_role,
        all_roles_list=all_roles_list,
        pending_event_context=pending_event_context,
        pending_event_ids=pending_event_ids
    )
    
    # Clear exception after it's been communicated to LLM
    if exception_feedback:
        exception_tracker.clear_exception()
    
    return result

# Patch choose_and_bind in llm_client module
llm_client_module.choose_and_bind = choose_and_bind_no_filtering

# Also patch in ahoy module where it might be imported
if hasattr(ahoy_module, 'choose_and_bind'):
    ahoy_module.choose_and_bind = choose_and_bind_no_filtering

# Wrap adapter.send() to catch kiko exceptions
original_send = None

async def send_with_exception_tracking(msg_instance):
    """
    Wrapper around adapter.send() that catches kiko exceptions
    and logs them for feedback to LLM.
    """
    global original_send
    try:
        return await original_send(msg_instance)
    except Exception as e:
        # Check if this is a BSPL/kiko protocol violation
        exc_str = str(e)
        exc_type = type(e).__name__
        
        # Log exception
        if hasattr(ahoy_module, 'log_debug'):
            ahoy_module.log_debug(f"EXCEPTION CAUGHT: {exc_type}: {exc_str}")
        
        # Track exception for next LLM decision
        exception_tracker = get_exception_tracker()
        exception_tracker.record_exception(exc_type, exc_str)
        
        # Log that we caught and logged the exception
        if hasattr(ahoy_module, 'log_debug'):
            ahoy_module.log_debug(f"Exception tracked and will be fed back to LLM on next decision")
        
        # Re-raise so the adapter knows the send failed
        # (This allows LLM to make a different choice on next decision)
        raise

# Import and run the standard ahoy agent
from agents.ahoy import main, adapter, llm_client, ui

if __name__ == "__main__":
    try:
        # Patch adapter.send() with exception tracking
        original_send = adapter.send
        adapter.send = send_with_exception_tracking
        
        # Run ahoy with exception-driven learning
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        ui.message("Baseline 2 (No Filtering) interrupted by user")
    except SystemExit as e:
        # Let completion signals propagate
        raise
    except Exception as e:
        ui.error_occurred(str(e))
        raise
