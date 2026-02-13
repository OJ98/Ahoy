#!/usr/bin/env python3
"""
Demo 4 Harness: Custom Events Integration Test

Demonstrates an LLM agent receiving and responding to an external event
(purchase request for a bat with delivery constraints) while executing a formal protocol.

Flow:
1. Setup environment and logging
2. Configure ahoy.py for Purchase:Buyer role
3. Launch agent and event injector concurrently
4. External system injects: "Buy a bat" event with delivery address and budget
5. Agent's LLM considers the external request when making purchase decisions
6. Collect metrics on event processing
7. Analyze results

Key Innovation: Agents can extend their decision context with external requests
without breaking protocol structure or modifying agent code.
"""

import asyncio
import json
import logging
import subprocess
import sys
import tempfile
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.llm_client import reset_llm_tracker, initialize_llm_tracker

# Demo files
sys.path.insert(0, str(Path(__file__).resolve().parent))
from event_simulator import InventorySystemSimulator
from event_analyzer import EventAnalyzer


# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

DEMO_RESULTS_DIR = Path(__file__).resolve().parent / "results"
DEMO_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = PROJECT_ROOT / "logs"
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
DEMO_LOG_FILE = DEMO_RESULTS_DIR / f"demo4_{RUN_TIMESTAMP}.log"
EVENTS_LOG_FILE = DEMO_RESULTS_DIR / f"demo4_events_{RUN_TIMESTAMP}.json"

# Protocol to test
PROTOCOL_CONFIG = {
    "name": "Purchase",
    "ahoy_role": "Buyer",
    "other_agents": ["seller.py", "shipper.py"],
    "input_file": PROJECT_ROOT / "input_purchase.txt",
    "description": "Purchase with real-time inventory events"
}

# Execution timeout
EXECUTION_TIMEOUT = 60  # seconds (allow protocol to execute after event injection)

# Global state
logger: Optional[logging.Logger] = None
debug_logger: Optional[logging.Logger] = None
all_metrics: List[Any] = []


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Configure logging for demo execution."""
    global logger, debug_logger
    
    debug_logger = logging.getLogger("demo4_debug")
    logger = logging.getLogger("demo4")
    
    debug_logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)
    
    debug_logger.handlers = []
    logger.handlers = []
    
    # File handler for debug logs
    debug_handler = logging.FileHandler(DEMO_LOG_FILE, mode='w')
    debug_handler.setLevel(logging.DEBUG)
    debug_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    debug_handler.setFormatter(debug_format)
    debug_logger.addHandler(debug_handler)
    
    # Console handler for info logs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '[%(asctime)s] [DEMO4] %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # Both loggers also log to both handlers
    debug_logger.addHandler(console_handler)


def log(message: str, level: str = "INFO"):
    """Log a message at specified level."""
    if logger:
        getattr(logger, level.lower())(message)
    if debug_logger:
        getattr(debug_logger, level.lower())(message)


# ============================================================================
# SETUP & CLEANUP
# ============================================================================

def clear_state():
    """Clear previous state files."""
    try:
        # Clear CHIPS config file FIRST (before anything else)
        # This ensures no stale config from previous runs affects the new session
        config_file = Path(tempfile.gettempdir()) / "maf_chips_config.txt"
        if config_file.exists():
            config_file.unlink()
        
        # Clear agent notes
        agent_notes_file = LOG_DIR / "agent_notes" / "agent_notes.json"
        if agent_notes_file.exists():
            agent_notes_file.write_text(json.dumps({}))
        
        # Clear stop signal
        stop_signal = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"
        if stop_signal.exists():
            stop_signal.unlink()
        
        # Clear events queue file
        events_queue = Path(tempfile.gettempdir()) / "maf_events_queue.json"
        if events_queue.exists():
            events_queue.unlink()
        
        # Clear termination conditions
        termination_conditions = Path(tempfile.gettempdir()) / "maf_termination_conditions.json"
        if termination_conditions.exists():
            termination_conditions.unlink()
        
        log("Previous state cleared")
    except Exception as e:
        log(f"Error clearing state: {e}", "WARNING")


def signal_stop():
    """Signal agents to stop."""
    try:
        stop_signal = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"
        stop_signal.write_text("stop")
        log("Stop signal written")
    except Exception as e:
        log(f"Error writing stop signal: {e}", "WARNING")


def find_most_recent_agent_log() -> Optional[Path]:
    """Find the most recent agent debug log file."""
    try:
        agent_logs = list(LOG_DIR.glob("generic_agent_debug_*.log"))
        if agent_logs:
            # Sort by modification time, get the most recent
            agent_logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            most_recent = agent_logs[0]
            log(f"Found agent debug log: {most_recent.name}")
            return most_recent
    except Exception as e:
        log(f"Error finding agent log: {e}", "WARNING")
    return None


# ============================================================================
# AGENT MANAGEMENT
# ============================================================================

def start_agents() -> List[Tuple[str, subprocess.Popen]]:
    """
    Start all agents for the protocol.
    ahoy.py for the main Buyer role, plus seller.py and shipper.py as supporting agents.
    
    Returns:
        List of (agent_name, Popen) tuples for running agents
    """
    log(f"Starting agents for {PROTOCOL_CONFIG['name']}...")
    
    processes = []
    
    # Write configuration for ahoy.py to temp directory
    # Format: "Protocol:Role" (e.g., "Purchase:Buyer")
    config_file = Path(tempfile.gettempdir()) / "maf_chips_config.txt"
    config_content = f"{PROTOCOL_CONFIG['name']}:{PROTOCOL_CONFIG['ahoy_role']}"
    config_file.write_text(config_content)
    log(f"Wrote config to {config_file}: {config_content}")
    
    # Copy protocol-specific input file to input.txt so ahoy.py reads the scenario
    if PROTOCOL_CONFIG["input_file"].exists():
        input_txt = PROJECT_ROOT / "input.txt"
        input_txt.write_text(PROTOCOL_CONFIG["input_file"].read_text())
        log(f"Wrote scenario input from {PROTOCOL_CONFIG['input_file']}")
    
    # Start ahoy.py for the main agent
    try:
        ahoy_path = PROJECT_ROOT / "agents" / "ahoy.py"
        if not ahoy_path.exists():
            log(f"ERROR: ahoy.py not found at {ahoy_path}", "ERROR")
            return processes
        
        proc = subprocess.Popen(
            [sys.executable, str(ahoy_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        processes.append(("ahoy.py", proc))
        log(f"Started ahoy.py (PID: {proc.pid})")
        time.sleep(2)  # Give ahoy time to initialize
    except Exception as e:
        log(f"Error starting ahoy.py: {e}", "ERROR")
        return processes
    
    # Start supporting agents (seller, shipper)
    for agent in PROTOCOL_CONFIG["other_agents"]:
        agent_name = agent.lower().replace('.py', '')
        agent_script = PROJECT_ROOT / "agents" / f"{agent_name}.py"
        
        if not agent_script.exists():
            log(f"Warning: Agent script not found: {agent_script}", "WARNING")
            continue
        
        try:
            proc = subprocess.Popen(
                [sys.executable, str(agent_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(PROJECT_ROOT)
            )
            processes.append((agent_name, proc))
            log(f"Started {agent_name} (PID: {proc.pid})")
            time.sleep(0.5)  # Stagger starts
        except Exception as e:
            log(f"Error starting {agent_name}: {e}", "ERROR")
    
    return processes


def terminate_agents(processes: List[Tuple[str, subprocess.Popen]]):
    """Gracefully terminate all agent processes."""
    log("Terminating agents...")
    
    for agent_name, proc in processes:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            log(f"Terminated {agent_name}")
        except Exception as e:
            log(f"Error terminating {agent_name}: {e}", "WARNING")


# ============================================================================
# MAIN DEMO EXECUTION
# ============================================================================

async def run_demo():
    """Main demo execution flow."""
    log("="*70)
    log("DEMO 4: Custom Events Integration")
    log("="*70)
    log(f"Protocol: {PROTOCOL_CONFIG['name']}")
    log(f"Main Role: {PROTOCOL_CONFIG['ahoy_role']}")
    log(f"Results: {DEMO_RESULTS_DIR}")
    log("="*70)
    
    # Setup
    setup_logging()
    initialize_llm_tracker(max_calls=50, max_duration_seconds=300.0)
    clear_state()
    
    # Start agents
    processes = start_agents()
    
    if not processes:
        log("ERROR: No agents started", "ERROR")
        return False
    
    # Create simulator
    simulator = InventorySystemSimulator(
        protocol=PROTOCOL_CONFIG["name"],
        role=PROTOCOL_CONFIG["ahoy_role"],
        log_file=DEMO_LOG_FILE
    )
    
    try:
        # Run agent and simulator concurrently
        log(f"Starting event injection for {PROTOCOL_CONFIG['ahoy_role']}...")
        
        start_time = time.time()
        
        # Run simulator (injects events)
        await asyncio.wait_for(
            simulator.inject_events(),
            timeout=EXECUTION_TIMEOUT
        )
        
        elapsed = time.time() - start_time
        log(f"Demo execution completed in {elapsed:.2f} seconds")
        
        # Save events log
        simulator.save_events_log(EVENTS_LOG_FILE)
        
        # Analyze results - use agent debug log, not harness log
        log("Analyzing results...")
        agent_log = find_most_recent_agent_log()
        analyzer = EventAnalyzer(agent_log or DEMO_LOG_FILE, EVENTS_LOG_FILE)
        analyzer.analyze()
        analyzer.print_summary()
        
        # Save analysis report
        report_file = DEMO_RESULTS_DIR / f"demo4_analysis_{RUN_TIMESTAMP}.json"
        analyzer.save_report(report_file)
        
        log(f"Analysis report saved to {report_file}")
        log("Demo 4 completed successfully!")
        
        return True
        
    except asyncio.TimeoutError:
        log(f"Execution timeout after {EXECUTION_TIMEOUT} seconds", "WARNING")
        log("This may indicate the protocol stalled (expected for demo)")
        
        # Still save analysis of partial execution
        simulator.save_events_log(EVENTS_LOG_FILE)
        agent_log = find_most_recent_agent_log()
        analyzer = EventAnalyzer(agent_log or DEMO_LOG_FILE, EVENTS_LOG_FILE)
        analyzer.analyze()
        analyzer.print_summary()
        
        report_file = DEMO_RESULTS_DIR / f"demo4_analysis_{RUN_TIMESTAMP}.json"
        analyzer.save_report(report_file)
        
        return True  # Timeout is expected for long-running protocols
        
    except Exception as e:
        log(f"ERROR during demo execution: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        return False
        
    finally:
        # Cleanup
        signal_stop()
        time.sleep(1)
        terminate_agents(processes)
        log("All agents terminated")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        success = asyncio.run(run_demo())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("Demo interrupted by user", "WARNING")
        sys.exit(1)
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        sys.exit(1)
