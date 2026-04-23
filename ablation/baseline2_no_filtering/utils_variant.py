#!/usr/bin/env python3
"""
Baseline 2 variant: No Filtering (Exception-Driven Learning)

Overrides enabled message filtering to show LLM ALL possible messages
in the protocol. Violations are caught via kiko exceptions, and the LLM
learns constraints through trial-and-error feedback.

Key differences:
1. Shows all possible messages instead of just enabled ones
2. Adds exception handler to catch kiko violations
3. Feeds exception feedback back to LLM in next decision cycle
"""

from typing import Dict, Any, List, Optional


class ExceptionTracker:
    """Track kiko exceptions for feedback to LLM."""
    
    def __init__(self):
        self.last_exception = None
        self.exception_history = []
    
    def record_exception(self, exc_type: str, exc_message: str):
        """Record an exception for next LLM decision."""
        self.last_exception = {
            "type": exc_type,
            "message": exc_message
        }
        self.exception_history.append(self.last_exception)
    
    def get_exception_feedback(self) -> str:
        """
        Generate feedback string about recent exceptions for LLM.
        
        Returns:
            String describing what went wrong with last message choice
        """
        if not self.last_exception:
            return ""
        
        exc = self.last_exception
        feedback = "\n⚠️  CONSTRAINT VIOLATION (from last decision):\n"
        feedback += f"  Exception Type: {exc['type']}\n"
        feedback += f"  Reason: {exc['message']}\n"
        feedback += f"  → Try a DIFFERENT message next time that respects this constraint.\n"
        
        return feedback
    
    def clear_exception(self):
        """Clear last exception after feedback is given to LLM."""
        self.last_exception = None


# Global exception tracker
_exception_tracker = ExceptionTracker()


def get_exception_tracker() -> ExceptionTracker:
    """Get global exception tracker."""
    return _exception_tracker


def expand_enabled_to_all_messages(adapter, current_role: str) -> List[Dict[str, Any]]:
    """
    Instead of filtering to enabled messages, show ALL possible messages
    for this role in the protocol.
    
    Args:
        adapter: BSPL adapter instance
        current_role: Current role name (e.g., "Buyer")
    
    Returns:
        List of all possible message options (unfiltered)
    """
    all_options = []
    option_idx = 0
    
    # Try to extract all message types from the protocol
    try:
        if hasattr(adapter, 'protocol') and hasattr(adapter.protocol, 'messages'):
            for msg_schema in adapter.protocol.messages:
                # Check if this role can send this message
                if hasattr(msg_schema, 'source'):
                    if hasattr(msg_schema.source, 'name'):
                        sender_name = msg_schema.source.name
                    else:
                        sender_name = str(msg_schema.source)
                    
                    if sender_name == current_role:
                        # This role can send this message - add to options
                        all_options.append({
                            "index": option_idx,
                            "schema_name": msg_schema.qualified_name if hasattr(msg_schema, 'qualified_name') else msg_schema.name,
                            "message_schema": msg_schema,
                            "note": "(unfiltered - may not be currently enabled)"
                        })
                        option_idx += 1
    except Exception as e:
        # Fallback: use enabled store even if we can't extract all
        pass
    
    return all_options if all_options else None


def format_exception_feedback_for_prompt(exception_feedback: str) -> str:
    """
    Format exception feedback to include in LLM user prompt.
    
    Args:
        exception_feedback: Raw exception feedback string
    
    Returns:
        Formatted string ready for inclusion in prompt
    """
    if not exception_feedback:
        return ""
    
    return f"""
{exception_feedback}
REMINDER: You are choosing from ALL POSSIBLE MESSAGES (not just enabled ones).
The protocol constraints will enforce which choices are actually valid.
Use exceptions as learning signals to avoid repeating the same invalid choice.
"""
