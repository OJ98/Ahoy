#!/usr/bin/env python3
"""
Minimal logging functions for the multi-agent system.
"""

import logging
import sys
from io import TextIOWrapper
from typing import Optional

# Ensure UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout = TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(log_filename: str, logger_name: str = "buyer_debug", console_logger_name: str = "buyer_console", mode: str = 'w'):
    """
    Configure debug file logging and console output logging.
    
    Args:
        log_filename: Path to the log file
        logger_name: Name of the debug logger
        console_logger_name: Name of the console logger
        mode: File open mode - 'w' (write/overwrite) or 'a' (append)
    """
    # Debug logger (file only)
    debug_logger = logging.getLogger(logger_name)
    debug_logger.setLevel(logging.DEBUG)
    debug_handler = logging.FileHandler(log_filename, mode=mode, encoding='utf-8')
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
    """Log a console message to stdout."""
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
    
    def error(self, message: str):
        """Display an error message."""
        self.logger.info(f"❌ {message}")
    
    def divider(self):
        """Display a divider line."""
        self.logger.info(f"\n{'─'*60}\n")
    
    def status_update(self, call_count: int, elapsed_seconds: float):
        """Display LLM status update."""
        self.logger.info(f"📊 LLM Calls: {call_count} | Time: {elapsed_seconds:.0f}s")
    
    def transaction_complete(self, total: int, rejected: int, accepted: int):
        """Display transaction completion summary."""
        self.logger.info(f"✅ Transaction Summary: Total={total}, Rejected={rejected}, Accepted={accepted}")
    
    def error_occurred(self, message: str):
        """Display error message."""
        self.logger.info(f"❌ Error: {message}")
    
    def interrupted(self):
        """Display interruption message."""
        self.logger.info(f"⚠️  Interrupted by user")
