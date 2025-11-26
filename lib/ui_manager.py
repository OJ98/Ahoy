#!/usr/bin/env python3
"""
UI and logging functions for the multi-agent system.
Manages console output, logging, and debug information display.
"""

import logging
import sys
import json
from typing import Optional, Any
from io import TextIOWrapper

# Ensure UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout = TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(log_filename: str, logger_name: str = "buyer_debug", console_logger_name: str = "buyer_console"):
    """Configure debug file logging and console output logging.
    
    Creates two separate loggers:
    - Debug logger: writes to file only
    - Console logger: writes to stdout only
    """
    # Debug logger (file only)
    debug_logger = logging.getLogger(logger_name)
    debug_logger.setLevel(logging.DEBUG)
    debug_handler = logging.FileHandler(log_filename, encoding='utf-8')
    debug_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    debug_logger.addHandler(debug_handler)
    debug_logger.propagate = False
    
    # Console logger (stdout only)
    console_logger = logging.getLogger(console_logger_name)
    console_logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    console_logger.addHandler(console_handler)
    console_logger.propagate = False
    
    # Suppress root logger
    logging.getLogger().setLevel(logging.CRITICAL)
    logging.getLogger().propagate = False
    
    return debug_logger, console_logger


# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

def _get_logger(name: str) -> logging.Logger:
    """Get a logger by name safely."""
    return logging.getLogger(name)


def log_debug(message: str, logger_name: str = "buyer_debug"):
    """Log a debug message to file only."""
    _get_logger(logger_name).debug(message)


def log_console(message: str, logger_name: str = "buyer_console"):
    """Log a console message to stdout and debug file."""
    _get_logger(logger_name).info(message)


# ============================================================================
# USER INTERFACE CLASS
# ============================================================================

class UserInterface:
    """Manages all user-facing console output with consistent formatting."""
    
    def __init__(self, console_logger_name: str = "buyer_console"):
        """Initialize with a console logger."""
        self.logger = logging.getLogger(console_logger_name)
    
    def header(self, title: str):
        """Display a formatted header section."""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"  {title}")
        self.logger.info(f"{'='*60}\n")
    
    def prompt(self, icon: str, message: str, sublabel: Optional[str] = None):
        """Display a prompt with optional sub-label."""
        self.logger.info(f"{icon} {message}")
        if sublabel:
            self.logger.info(f"   {sublabel}\n")
    
    def info(self, icon: str, message: str):
        """Display an info message."""
        self.logger.info(f"{icon} {message}")
    
    def success(self, icon: str, message: str):
        """Display a success message."""
        self.logger.info(f"{icon} {message}")
    
    def error(self, message: str):
        """Display an error message."""
        self.logger.info(f"❌ {message}")
    
    def divider(self):
        """Display a blank line divider."""
        self.logger.info("")
    
    def processing_in_background(self, action: str = "processing"):
        """Show progress indicator for background work."""
        self.logger.info(f"⏳ {action.capitalize()}...")
    
    # Workflow-specific methods
    
    def start_requirements(self):
        """Prompt for initial system requirements."""
        self.header("System Configuration")
        self.prompt("📋", "Enter your system requirements and priorities:", "(Type 'done' when finished)")
    
    def ask_refine_requirements(self):
        """Ask if user wants to refine requirements."""
        self.prompt("❓", "Refine requirements? (yes/no)")
    
    def prompt_additional_requirements(self):
        """Prompt for additional requirements."""
        self.prompt("📝", "Add more requirements:", "(Type 'done' when finished)")
    
    def show_analysis(self, analysis: str):
        """Display LLM analysis results."""
        self.divider()
        self.logger.info("📊 Analysis:")
        self.logger.info("-" * 60)
        self.logger.info(analysis)
        self.logger.info("-" * 60)
        self.divider()
    
    def transaction_complete(self, total: int, rejections: int, deliveries: int):
        """Display transaction completion summary."""
        self.divider()
        if total > 0:
            self.success("✅", f"Complete: {total} transactions ({rejections}❌ {deliveries}✓)")
        else:
            self.info("⏸", "No transactions processed")
        self.divider()
    
    def interrupted(self):
        """Display interruption message."""
        self.error("Interrupted by user")
        self.divider()
    
    def error_occurred(self, error: str):
        """Display error message."""
        self.error(f"Error: {error}")
        self.divider()
    
    def show_log_location(self, filepath: str):
        """Display the debug log file path."""
        self.info("📁", f"Debug log: {filepath}")
    
    def show_role_inferred(self, role: str):
        """Display the inferred agent role."""
        self.info("🎯", f"Role: {role}")
    
    def status_update(self, message_count: int, elapsed_seconds: float):
        """Display minimal status update with message count and elapsed time."""
        self.info("📊", f"{message_count} messages, {elapsed_seconds:.0f}s elapsed")


# ============================================================================
# DEBUG OUTPUT FUNCTIONS
# ============================================================================

def _format_set_value(s: set) -> str:
    """Format a set as a readable string."""
    items = [str(item) for item in s]
    return f"<set with {len(s)} items>: {items}"


def _format_object_attributes(obj: Any) -> dict:
    """Extract public attributes from an object, formatting sets specially."""
    attrs = {}
    if hasattr(obj, '__dict__'):
        for key, value in obj.__dict__.items():
            if key.startswith('_'):
                continue
            if isinstance(value, set):
                attrs[key] = _format_set_value(value)
            else:
                attrs[key] = value
    return attrs


def print_event_debug(event: Any, debug_logger_name: str = "buyer_debug"):
    """Log event object details in readable form to debug log.
    
    Handles both dict and object events, with special formatting for sets.
    """
    debug_logger = _get_logger(debug_logger_name)
    
    try:
        lines = ["=" * 50, "Event Debug Info:", f"Type: {type(event).__name__}"]
        
        if isinstance(event, dict):
            # Format dict with special handling for sets
            formatted = {}
            for key, value in event.items():
                formatted[key] = _format_set_value(value) if isinstance(value, set) else value
            lines.append(json.dumps(formatted, indent=2, default=str))
        else:
            # Format object with attributes
            lines.append(str(event))
            attrs = _format_object_attributes(event)
            if attrs:
                lines.append(json.dumps(attrs, indent=2, default=str))
        
        lines.append("=" * 50)
        for line in lines:
            debug_logger.debug(line)
    except Exception as e:
        debug_logger.debug(f"Error logging event: {e}")


def print_enabled_store_debug(enabled_store: Any, debug_logger_name: str = "buyer_debug"):
    """Log all available messages in the enabled store.
    
    Shows schema, sender, recipients, and parameter binding status.
    """
    debug_logger = _get_logger(debug_logger_name)
    
    try:
        messages = list(enabled_store.messages())
        lines = [
            "=" * 80,
            f"Enabled Store ({len(messages)} message(s))",
            "=" * 80
        ]
        
        for idx, partial in enumerate(messages):
            lines.append("")
            lines.append(f"[{idx}] {partial.schema.qualified_name}")
            lines.append(f"    From: {partial.schema.sender.name}")
            lines.append(f"    To: {', '.join(r.name for r in partial.schema.recipients)}")
            lines.append("    Parameters:")
            
            for param_name in partial.schema.parameters:
                bound = partial.bindings.get(param_name)
                status = "MISSING" if bound is None else "BOUND"
                lines.append(f"        {param_name}: {bound} [{status}]")
        
        lines.append("")
        lines.append("=" * 80)
        for line in lines:
            debug_logger.debug(line)
    except Exception as e:
        debug_logger.debug(f"Error logging enabled store: {e}")


def print_user_prompt(prompt: str, debug_logger_name: str = "buyer_debug", title: str = "USER PROMPT"):
    """Log the constructed user prompt to debug log."""
    debug_logger = _get_logger(debug_logger_name)
    debug_logger.debug(f"{'='*80}")
    debug_logger.debug(f"{title}")
    debug_logger.debug(f"{'='*80}")
    debug_logger.debug(prompt)
    debug_logger.debug(f"{'='*80}")


def print_llm_response(response: Any, debug_logger_name: str = "buyer_debug", title: str = "LLM RESPONSE"):
    """Log LLM response in readable format to debug log.
    
    Handles tuples, JSON strings, and plain strings with appropriate formatting.
    """
    debug_logger = _get_logger(debug_logger_name)
    debug_logger.debug(f"{'='*80}")
    debug_logger.debug(f"{title}")
    debug_logger.debug(f"{'='*80}")
    
    # Format based on response type
    if isinstance(response, tuple):
        # Tuple response: (choice, params)
        choice_idx, params = response
        output = {"choice": choice_idx, "params": params}
        debug_logger.debug(json.dumps(output, indent=2))
    elif isinstance(response, str):
        # Try JSON parsing, fall back to plain string
        try:
            parsed = json.loads(response)
            debug_logger.debug(json.dumps(parsed, indent=2))
        except (json.JSONDecodeError, ValueError):
            debug_logger.debug(response)
    else:
        # Other types: convert to string
        debug_logger.debug(str(response))
    
    debug_logger.debug(f"{'='*80}")
