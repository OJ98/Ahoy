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

# Initialize the agent notes system for tracking decisions and actions
notes = get_agent_notes('Buyer')

deliveries = 0
rejections = 0
accepted_deals = 0  # Track successful accepts


# ============================================================================
# MESSAGE OBSERVERS: Track protocol progression (using adapter.publish listener)
# ============================================================================

# We'll add message tracking via the adapter's publish mechanism in the main loop


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
    """
    log_debug(f"DEBUG: llm_decision called")
    log_debug(f"  - enabled_store type: {type(enabled_store)}")
    log_debug(f"  - event type: {type(event)}")
    
    # Fallback requirement callback (system prompt should be cached)
    async def fallback_callback(roles):
        return "Buyer", "You are a buyer agent. Make prudent purchasing decisions."
    
    # Log event details
    print_event_debug(event)
    
    # Check if enabled_store has any messages
    if not enabled_store:
        log_debug("DEBUG: No enabled_store available, skipping decision")
        return None
    
    messages = list(enabled_store.messages())
    log_debug(f"DEBUG: Found {len(messages)} enabled messages")
    
    if not messages:
        log_debug("DEBUG: No enabled messages available, skipping decision")
        return None
    
    log_debug("LLM decision invoked, enabled messages available.")
    print_enabled_store_debug(enabled_store)
    
    # Check for threshold before calling LLM
    tracker = get_llm_tracker()
    if tracker:
        exceeded, reason = tracker.check_threshold_exceeded()
        if exceeded:
            log_debug(f"Threshold exceeded: {reason}")
            ui.error(f"Threshold exceeded: {reason}")
            ui.divider()
            # Gracefully terminate
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
    
    # Display status update after LLM call
    if tracker:
        status = tracker.get_status()
        ui.status_update(tracker.call_count, tracker.get_elapsed_seconds())
        log_debug(f"Status: {status}")
    
    # Check for threshold after LLM call
    if tracker:
        exceeded, reason = tracker.check_threshold_exceeded()
        if exceeded:
            log_debug(f"Threshold exceeded: {reason}")
            ui.error(f"Threshold exceeded: {reason}")
            ui.divider()
            # Gracefully terminate
            raise SystemExit(f"Graceful termination: {reason}")
    
    log_debug(f"DEBUG: choose_and_bind returned: {instance}")
    
    if instance is None:
        log_debug("DEBUG: No instance returned from LLM, skipping")
        return None

    log_debug(f"DEBUG: Sending message: {instance}")
    
    # Track important messages using agent notes
    if hasattr(instance, 'schema') and hasattr(instance.schema, 'name'):
        msg_type = instance.schema.name
        notes = get_agent_notes_tracker('Buyer')
        tracker = get_llm_tracker()
        llm_call_num = tracker.call_count if tracker else 0
        
        # Helper to get parameter value from either Message or Partial object
        def get_param(obj, param_name):
            if hasattr(obj, 'bindings') and obj.bindings:
                return obj.bindings.get(param_name)
            # Try accessing as dict key (Message objects might support this)
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
        
        # Track RFQ messages
        if msg_type == 'rfq':
            if notes:
                rfq_id = get_param(instance, 'ID')
                item = get_param(instance, 'item')
                notes.note_message('rfq', id=rfq_id, item=item, llm_call=llm_call_num)
                log_debug(f"[NOTED] RFQ sent: ID={rfq_id}, item={item}")
        
        # Track quote responses (received from seller)
        elif msg_type == 'quote':
            if notes:
                rfq_id = get_param(instance, 'ID')
                price = get_param(instance, 'price')
                notes.note_message('quote', rfq_id=rfq_id, price=price, llm_call=llm_call_num)
                log_debug(f"[NOTED] Quote received: ID={rfq_id}, price=${price}")
        
        # Track accept decisions
        elif msg_type == 'accept':
            if notes:
                transaction_id = get_param(instance, 'ID')
                item = get_param(instance, 'item')
                price = get_param(instance, 'price')
                notes.note_message('accept', id=transaction_id, item=item, price=price, llm_call=llm_call_num)
                log_debug(f"[NOTED] Accept decision: ID={transaction_id}, item={item}, price=${price}")
        
        # Track reject decisions
        elif msg_type == 'reject':
            if notes:
                transaction_id = get_param(instance, 'ID')
                item = get_param(instance, 'item')
                price = get_param(instance, 'price')
                outcome = get_param(instance, 'outcome')
                notes.note_message('reject', id=transaction_id, item=item, price=price, reason=outcome, llm_call=llm_call_num)
                log_debug(f"[NOTED] Reject decision: ID={transaction_id}, reason={outcome}")
        
        # Track delivery confirmations
        elif msg_type == 'deliver':
            if notes:
                transaction_id = get_param(instance, 'ID')
                item = get_param(instance, 'item')
                outcome = get_param(instance, 'outcome')
                notes.note_message('deliver', id=transaction_id, item=item, status=outcome, llm_call=llm_call_num)
                log_debug(f"[NOTED] Delivery: ID={transaction_id}, outcome={outcome}")
        
        # Track completion message
        elif msg_type == 'completed':
            log_debug(f"[GOAL ACHIEVED] LLM sent completion signal: {instance}")
            if notes:
                notes.note_message('completed', id=get_param(instance, 'ID'), item=get_param(instance, 'item'), 
                                   price=get_param(instance, 'price'), satisfaction=get_param(instance, 'satisfaction'), 
                                   llm_call=llm_call_num)
            
            # Create stop signal for all agents
            try:
                with open(".stop_signal", "w") as f:
                    f.write("transaction_complete")
                log_debug("Stop signal created - all agents will shut down")
            except Exception as e:
                log_debug(f"Error creating stop signal: {e}")
            
            raise SystemExit(f"✅ Goal achieved: LLM marked transaction complete. {instance}")
    
    return instance


if __name__ == "__main__":
    try:
        # Initialize the LLM call tracker with thresholds: 20 calls or 3 minutes (180 seconds)
        initialize_llm_tracker(max_calls=20, max_duration_seconds=180.0)
        log_debug("LLM tracker initialized: max 20 calls or 3 minutes")
        
        # Initialize agent notes tracker for general-purpose note tracking
        notes_tracker = get_agent_notes_tracker('Buyer')
        log_debug("Agent notes tracker initialized with JSON file tracking")
        
        # Initialize system prompt BEFORE starting the adapter
        # This ensures it's cached before the first decision event
        import asyncio as _asyncio
        role, system_prompt = _asyncio.run(initialize_buyer_with_llm())
        
        if not role:
            ui.error_occurred("Failed to initialize buyer")
        else:
            # Now start the adapter with the cached system prompt
            adapter.start(main())
            total = rejections + accepted_deals + deliveries
            if total > 0:
                ui.transaction_complete(total, rejections, accepted_deals)
                log_debug(f"[FINAL] Transactions: Total={total}, Rejected={rejections}, Accepted={accepted_deals}, Delivered={deliveries}")
            else:
                ui.info("⏸", "No transactions processed")
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
        
        # Show final statistics
        total = rejections + accepted_deals + deliveries
        if total > 0:
            ui.transaction_complete(total, rejections, accepted_deals)
            log_debug(f"[FINAL] Transactions: Total={total}, Rejected={rejections}, Accepted={accepted_deals}, Delivered={deliveries}")
        
        # Show agent notes summary
        if notes:
            summary = notes.get_summary()
            notes.export(f"./logs/buyer_notes_{timestamp}.json")
            log_debug(f"\n[AGENT NOTES SUMMARY]\n{json.dumps(summary, indent=2)}")
            ui.info("📝", f"Agent notes exported: logs/buyer_notes_{timestamp}.json")
    except Exception as e:
        ui.error_occurred(str(e))
        log_debug(f"Full traceback:\n{traceback.format_exc()}")
    finally:
        ui.show_log_location(log_filename)
        for handler in debug_logger.handlers:
            handler.close()
        for handler in console_logger.handlers:
            handler.close()
