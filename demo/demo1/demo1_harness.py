#!/usr/bin/env python3
"""
Demo 1 Harness (LLM-Enabled): Sequential Multi-Protocol Execution with ahoy.py
Runs Purchase Protocol (Buyer) followed by Logistics Protocol (Merchant) using LLM.

Flow:
1. Configure ahoy.py for Purchase:Buyer
2. Execute Purchase Protocol with comprehensive logging
3. Clean up and reset state
4. Configure ahoy.py for Logistics:Merchant
5. Execute Logistics Protocol with comprehensive logging
6. Analyze results with full LLM metrics and decision logs
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

# Add project root to path (demo1 is two levels deep: demo/demo1/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.llm_client import get_llm_tracker, reset_llm_tracker, initialize_llm_tracker


# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

DEMO_RESULTS_DIR = Path(__file__).resolve().parent / "results"
DEMO_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = PROJECT_ROOT / "logs"

# Timestamp for this demo run
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
DEMO_LOG_FILE = DEMO_RESULTS_DIR / f"demo1_{RUN_TIMESTAMP}.log"

# Protocols to run in sequence with their ahoy.py role
PROTOCOLS = [
    {
        "name": "Purchase",
        "ahoy_role": "Buyer",
        "other_agents": ["seller.py", "shipper.py"],  # Start these in addition to ahoy.py
        "input_file": PROJECT_ROOT / "input_purchase.txt",
        "description": "E-commerce: Buyer-Seller-Shipper transaction"
    },
    {
        "name": "Logistics",
        "ahoy_role": "Merchant",
        "other_agents": ["packer.py", "labeler.py", "wrapper.py"],  # Start these in addition to ahoy.py
        "input_file": PROJECT_ROOT / "input_logistics.txt",
        "description": "Supply chain: Merchant order fulfillment"
    }
]

# Global logging and metrics setup
logger: Optional[logging.Logger] = None
debug_logger: Optional[logging.Logger] = None
all_metrics: List[Any] = []  # Populated during main() execution


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Configure detailed logging for demo execution."""
    global logger, debug_logger
    
    # Create loggers
    debug_logger = logging.getLogger("demo_debug")
    logger = logging.getLogger("demo")
    
    # Set level
    debug_logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    debug_logger.handlers = []
    logger.handlers = []
    
    # File handler for debug logs (detailed)
    debug_handler = logging.FileHandler(DEMO_LOG_FILE, mode='w')
    debug_handler.setLevel(logging.DEBUG)
    debug_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    debug_handler.setFormatter(debug_format)
    debug_logger.addHandler(debug_handler)
    
    # Console handler (info level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    logger.addHandler(debug_handler)  # Also log info to file
    
    return debug_logger, logger


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

def write_ahoy_config(protocol_name: str, role_name: str, input_file: Optional[Path] = None) -> None:
    """
    Write ahoy.py configuration to temp file and optionally copy scenario input.
    
    Args:
        protocol_name: Protocol name (e.g., "Purchase")
        role_name: Role name (e.g., "Buyer")
        input_file: Optional path to protocol-specific input file
    """
    config_file = Path(tempfile.gettempdir()) / "maf_chips_config.txt"
    config_content = f"{protocol_name}:{role_name}"
    
    try:
        config_file.write_text(config_content)
        debug_logger.debug(f"Wrote ahoy config: {config_file} = {config_content}")
        
        # Copy protocol-specific input file to input.txt so ahoy.py reads it
        if input_file and input_file.exists():
            input_txt = PROJECT_ROOT / "input.txt"
            input_txt.write_text(input_file.read_text())
            debug_logger.debug(f"Wrote scenario input: {input_file.name} -> input.txt")
        
    except Exception as e:
        debug_logger.error(f"Failed to write config: {e}")
        raise


def clear_ahoy_config() -> None:
    """Clear ahoy.py configuration."""
    config_file = Path(tempfile.gettempdir()) / "maf_chips_config.txt"
    if config_file.exists():
        try:
            config_file.unlink()
            debug_logger.debug(f"Cleared config file: {config_file}")
        except Exception as e:
            debug_logger.warning(f"Failed to clear config: {e}")


def get_stop_signal_path() -> Path:
    """Get platform-agnostic stop signal path."""
    return Path(tempfile.gettempdir()) / "maf_stop_signal.txt"


def clear_stop_signal():
    """Clear any existing stop signal."""
    stop_path = get_stop_signal_path()
    if stop_path.exists():
        try:
            stop_path.unlink()
            debug_logger.debug(f"Cleared stop signal: {stop_path}")
        except Exception as e:
            debug_logger.warning(f"Failed to clear stop signal: {e}")


def set_stop_signal():
    """Set the stop signal to terminate agents."""
    stop_path = get_stop_signal_path()
    try:
        stop_path.write_text("STOP")
        debug_logger.debug(f"Set stop signal: {stop_path}")
    except Exception as e:
        debug_logger.error(f"Failed to set stop signal: {e}")


# ============================================================================
# AHOY AGENT MANAGEMENT
# ============================================================================

def start_ahoy_agent(protocol_name: str, role_name: str, input_file: Optional[Path] = None) -> subprocess.Popen:
    """
    Start ahoy.py agent configured for a specific protocol and role.
    
    Args:
        protocol_name: Protocol name (e.g., "Purchase")
        role_name: Role name (e.g., "Buyer")
        input_file: Optional path to protocol-specific input file
        
    Returns:
        Process object
    """
    # Write config for ahoy and copy scenario input
    write_ahoy_config(protocol_name, role_name, input_file)
    
    ahoy_path = PROJECT_ROOT / "agents" / "ahoy.py"
    
    if not ahoy_path.exists():
        raise FileNotFoundError(f"ahoy.py not found: {ahoy_path}")
    
    logger.info(f"Starting ahoy.py for {protocol_name}:{role_name}...")
    debug_logger.debug(f"ahoy.py path: {ahoy_path}")
    
    try:
        process = subprocess.Popen(
            [sys.executable, str(ahoy_path)],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        logger.info(f"  [OK] ahoy.py started (PID: {process.pid}) for {protocol_name}:{role_name}")
        debug_logger.debug(f"ahoy.py process PID: {process.pid}")
        
        # Give agent time to initialize
        time.sleep(2)
        
        return process
        
    except Exception as e:
        logger.error(f"Failed to start ahoy.py: {e}")
        debug_logger.error(f"Exception starting ahoy.py: {e}", exc_info=True)
        raise


def terminate_agent(process: subprocess.Popen):
    """Gracefully terminate agent process."""
    try:
        process.terminate()
        debug_logger.debug(f"Terminated process {process.pid}")
        
        # Wait for graceful shutdown
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            debug_logger.debug(f"Force killed process {process.pid}")
            
    except Exception as e:
        debug_logger.warning(f"Error terminating process: {e}")


def start_other_agents(protocol_name: str, agent_scripts: List[str]) -> List[subprocess.Popen]:
    """
    Start other hardcoded agents for the protocol.
    
    Args:
        protocol_name: Protocol name for logging
        agent_scripts: List of agent script names (e.g., ["seller.py", "shipper.py"])
        
    Returns:
        List of started process objects
    """
    processes = []
    agents_dir = PROJECT_ROOT / "agents"
    
    if agent_scripts:
        logger.info(f"Starting other agents for {protocol_name}...")
        debug_logger.debug(f"Agent scripts: {agent_scripts}")
    
    for agent_script in agent_scripts:
        agent_path = agents_dir / agent_script
        
        if not agent_path.exists():
            logger.error(f"Agent script not found: {agent_path}")
            continue
        
        try:
            process = subprocess.Popen(
                [sys.executable, str(agent_path)],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            processes.append(process)
            debug_logger.debug(f"Started agent process: {agent_script} (PID: {process.pid})")
            logger.info(f"  [OK] {agent_script} started (PID: {process.pid})")
            
        except Exception as e:
            logger.error(f"Failed to start agent {agent_script}: {e}")
            debug_logger.error(f"Exception starting {agent_script}: {e}", exc_info=True)
    
    # Give agents time to initialize
    if processes:
        time.sleep(1)
    
    return processes


def terminate_agents(processes: List[subprocess.Popen]):
    """Gracefully terminate all agent processes."""
    for process in processes:
        try:
            terminate_agent(process)
        except Exception as e:
            debug_logger.warning(f"Error terminating process: {e}")


# ============================================================================
# LOG COLLECTION & AGGREGATION
# ============================================================================

def get_latest_agent_log() -> Optional[Path]:
    """
    Get the most recent ahoy.py agent log file.
    
    Returns:
        Path to log file or None
    """
    logs_dir = PROJECT_ROOT / "logs"
    if logs_dir.exists():
        log_files = sorted(logs_dir.glob("generic_agent_debug_*.log"), reverse=True)
        if log_files:
            return log_files[0]
    return None


def append_agent_log_to_demo_log(protocol_name: str, role_name: str) -> None:
    """
    Append agent's detailed log to demo log file.
    
    Args:
        protocol_name: Protocol name
        role_name: Role name being executed
    """
    agent_log = get_latest_agent_log()
    if not agent_log:
        debug_logger.warning(f"No agent log found for {protocol_name}:{role_name}")
        return
    
    try:
        with open(DEMO_LOG_FILE, 'a', encoding='utf-8', errors='ignore') as demo_file:
            demo_file.write(f"\n{'='*70}\n")
            demo_file.write(f"AHOY.PY DETAILED LOG ({protocol_name}:{role_name})\n")
            demo_file.write(f"{'='*70}\n\n")
            
            with open(agent_log, 'r', encoding='utf-8', errors='ignore') as agent_file:
                demo_file.write(agent_file.read())
            
            demo_file.write(f"\n{'='*70}\n")
            demo_file.write(f"END AHOY.PY LOG\n")
            demo_file.write(f"{'='*70}\n\n")
        
        debug_logger.debug(f"Appended agent log: {agent_log}")
        
    except Exception as e:
        debug_logger.warning(f"Failed to append agent log: {e}")

@dataclass
class ProtocolMetrics:
    """Metrics for a single protocol execution."""
    protocol_name: str
    role_name: str
    execution_time: float
    llm_call_count: int
    llm_duration_seconds: float
    success: bool
    error_message: Optional[str] = None


async def execute_protocol(
    protocol_config: Dict[str, Any],
    max_wait_time: int = 60
) -> ProtocolMetrics:
    """
    Execute a single protocol with ahoy.py and other agents.
    
    Args:
        protocol_config: Protocol configuration
        max_wait_time: Maximum time to wait for protocol completion
        
    Returns:
        ProtocolMetrics with execution details
    """
    protocol_name = protocol_config['name']
    ahoy_role = protocol_config['ahoy_role']
    other_agents = protocol_config.get('other_agents', [])
    input_file = protocol_config.get('input_file')
    
    logger.info(f"\n{'='*70}")
    logger.info(f"Executing Protocol: {protocol_name} (ahoy.py Role: {ahoy_role})")
    logger.info(f"{'='*70}\n")
    
    # Clear state from previous run
    clear_stop_signal()
    reset_llm_tracker()
    initialize_llm_tracker(max_calls=20, max_duration_seconds=180)
    
    start_time = time.time()
    ahoy_process = None
    other_processes = []
    
    try:
        # Start other agents first
        other_processes = start_other_agents(protocol_name, other_agents)
        
        # Then start ahoy.py agent
        ahoy_process = start_ahoy_agent(protocol_name, ahoy_role, input_file)
        
        # Wait for protocol completion
        logger.info(f"Waiting for {protocol_name} protocol to complete...")
        debug_logger.debug(f"Monitoring with timeout: {max_wait_time}s")
        
        elapsed = 0
        poll_interval = 1
        protocol_complete = False
        
        while elapsed < max_wait_time:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            
            # Check if ahoy process has exited (indicates protocol completion)
            if ahoy_process.poll() is not None:
                protocol_complete = True
                logger.info(f"Protocol {protocol_name} completed (process exited).")
                break
        
        execution_time = time.time() - start_time
        
        if not protocol_complete:
            logger.warning(f"Protocol {protocol_name} did not complete within {max_wait_time}s, terminating...")
            set_stop_signal()
            await asyncio.sleep(1)
        
        # Append agent's detailed log to demo log
        append_agent_log_to_demo_log(protocol_name, ahoy_role)
        
        # Wait a moment for log file to be fully written
        await asyncio.sleep(0.5)
        
        # Collect LLM metrics from agent logs (not process tracker, since ahoy.py is a subprocess)
        # Get the agent log AFTER appending to ensure it's been written
        agent_log = get_latest_agent_log()
        llm_call_count = count_llm_calls_from_log(agent_log)
        
        # Use execution time as proxy for LLM duration since subprocess tracking doesn't work across process boundary
        llm_duration = execution_time
        
        # Check for successful execution
        execution_successful = check_execution_success(protocol_name, ahoy_role)
        
        # Log completion summary
        logger.info(f"\nProtocol Metrics for {protocol_name}:")
        logger.info(f"  Execution Time: {execution_time:.2f}s")
        logger.info(f"  LLM Calls: {llm_call_count}")
        logger.info(f"  LLM Duration: {llm_duration:.2f}s")
        logger.info(f"  Success: {execution_successful}")
        
        return ProtocolMetrics(
            protocol_name=protocol_name,
            role_name=ahoy_role,
            execution_time=execution_time,
            llm_call_count=llm_call_count,
            llm_duration_seconds=llm_duration,
            success=execution_successful,
            error_message=None if execution_successful else "No messages sent"
        )
        
    except Exception as e:
        logger.error(f"Error executing protocol {protocol_name}: {e}")
        debug_logger.error(f"Exception during protocol execution: {e}", exc_info=True)
        set_stop_signal()
        
        return ProtocolMetrics(
            protocol_name=protocol_name,
            role_name=ahoy_role,
            execution_time=time.time() - start_time,
            llm_call_count=0,
            llm_duration_seconds=0,
            success=False,
            error_message=str(e)
        )
        
    finally:
        # Always terminate all agents
        if ahoy_process:
            try:
                terminate_agent(ahoy_process)
            except Exception as e:
                debug_logger.debug(f"Error terminating ahoy process: {e}")
        
        if other_processes:
            try:
                terminate_agents(other_processes)
            except Exception as e:
                debug_logger.debug(f"Error terminating other agents: {e}")
        
        try:
            set_stop_signal()
        except Exception as e:
            debug_logger.debug(f"Error setting stop signal: {e}")
        
        try:
            clear_ahoy_config()
        except Exception as e:
            debug_logger.debug(f"Error clearing config: {e}")


def count_llm_calls_from_log(agent_log: Optional[Path]) -> int:
    """
    Count LLM calls from agent log file by looking for RAW LLM RESPONSE markers.
    
    Args:
        agent_log: Path to agent log file
        
    Returns:
        Number of LLM calls (RAW LLM RESPONSE occurrences)
    """
    if not agent_log or not agent_log.exists():
        return 0
    
    try:
        with open(agent_log, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Count occurrences of RAW LLM RESPONSE
            return content.count('RAW LLM RESPONSE')
    except Exception as e:
        debug_logger.warning(f"Failed to count LLM calls from log: {e}")
        return 0


def check_execution_success(protocol_name: str, role_name: str) -> bool:
    """
    Check if protocol execution was successful by parsing agent logs.
    Success = at least one message was sent (evidence of LLM responses).
    
    Args:
        protocol_name: Protocol name
        role_name: Role name
        
    Returns:
        True if messages were sent, False otherwise
    """
    agent_log = get_latest_agent_log()
    if not agent_log:
        return False
    
    try:
        with open(agent_log, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Success indicators: agent sent at least one message
            # This shows up as "Sending message:" in the logs
            success_indicators = [
                "Sending message:",
                "RAW LLM RESPONSE",  # At least one LLM decision was made
            ]
            return any(indicator in content for indicator in success_indicators)
    except Exception as e:
        debug_logger.warning(f"Failed to check execution success: {e}")
        return False


def run_analysis():
    """
    Run the analysis script on the latest demo results.
    Executes demo1_analysis.py to generate insights from the demo run.
    Passes the aggregated log file for analysis.
    """
    analysis_script = Path(__file__).resolve().parent / "demo1_analysis.py"
    if not analysis_script.exists():
        logger.warning(f"Analysis script not found: {analysis_script}")
        return
    
    try:
        logger.info(f"Executing: {analysis_script.name}")
        debug_logger.debug(f"Full path: {analysis_script}")
        debug_logger.debug(f"Analyzing log file: {DEMO_LOG_FILE}")
        
        # Create a temporary JSON file with metrics that the analysis script expects
        import tempfile
        metrics_data = {
            "run_timestamp": RUN_TIMESTAMP,
            "metrics": [asdict(m) for m in all_metrics],
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, dir=DEMO_RESULTS_DIR) as f:
            json.dump(metrics_data, f)
            temp_metrics_file = f.name
        
        # Run analysis script
        result = subprocess.run(
            [sys.executable, str(analysis_script), temp_metrics_file],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip():
                    logger.info(f"  {line}")
        
        if result.returncode != 0 and result.stderr:
            logger.warning(f"Analysis stderr: {result.stderr}")
        
        # Clean up temp file
        try:
            Path(temp_metrics_file).unlink()
        except:
            pass
            
    except subprocess.TimeoutExpired:
        logger.warning("Analysis script timed out (>30s)")
    except Exception as e:
        logger.warning(f"Failed to run analysis: {e}")
        debug_logger.debug(f"Error: {e}", exc_info=True)


# ============================================================================
# MAIN DEMO HARNESS
# ============================================================================

async def main():
    """Main demo harness execution."""
    global logger, debug_logger, all_metrics
    
    # Setup logging
    debug_logger, logger = setup_logging()
    
    logger.info("="*70)
    logger.info("DEMO 1: Sequential Multi-Protocol Execution with LLM (ahoy.py)")
    logger.info("="*70)
    logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Results Directory: {DEMO_RESULTS_DIR}")
    logger.info(f"Log File: {DEMO_LOG_FILE}")
    debug_logger.debug(f"Project Root: {PROJECT_ROOT}")
    
    all_metrics = []
    
    try:
        # Execute each protocol in sequence
        for i, protocol_config in enumerate(PROTOCOLS, 1):
            logger.info(f"\n{'='*70}")
            logger.info(f"Protocol {i}/{len(PROTOCOLS)}: {protocol_config['name']}")
            logger.info(f"{'='*70}\n")
            
            metrics = await execute_protocol(protocol_config)
            all_metrics.append(metrics)
            
            # Pause between protocols for cleanup
            if i < len(PROTOCOLS):
                logger.info(f"\nPausing for cleanup before next protocol...")
                await asyncio.sleep(2)
        
        # Save results
        logger.info(f"\n{'='*70}")
        logger.info("Saving Results")
        logger.info(f"{'='*70}\n")
        
        with open(DEMO_LOG_FILE, 'a', encoding='utf-8', errors='ignore') as f:
            f.write(f"\n\n{'='*70}\n")
            f.write(f"DEMO 1 EXECUTION COMPLETE\n")
            f.write(f"Run Timestamp: {RUN_TIMESTAMP}\n")
            f.write(f"Total Protocols: {len(all_metrics)}\n")
            f.write(f"Successful: {sum(1 for m in all_metrics if m.success)}\n")
            f.write(f"Total Execution Time: {sum(m.execution_time for m in all_metrics):.2f}s\n")
            f.write(f"{'='*70}\n\n")
        
        logger.info(f"Aggregated log saved to: {DEMO_LOG_FILE}")
        debug_logger.debug(f"Log file size: {DEMO_LOG_FILE.stat().st_size / 1024:.1f} KB")
        
        # Print summary
        logger.info(f"\n{'='*70}")
        logger.info("DEMO 1 SUMMARY")
        logger.info(f"{'='*70}\n")
        
        total_time = sum(m.execution_time for m in all_metrics)
        total_llm_calls = sum(m.llm_call_count for m in all_metrics)
        total_llm_duration = sum(m.llm_duration_seconds for m in all_metrics)
        successful = sum(1 for m in all_metrics if m.success)
        
        logger.info(f"Protocols Executed: {len(all_metrics)}")
        logger.info(f"Protocols Successful: {successful}/{len(all_metrics)}")
        logger.info(f"Total Execution Time: {total_time:.2f}s")
        logger.info(f"Total LLM Calls: {total_llm_calls}")
        logger.info(f"Total LLM Duration: {total_llm_duration:.2f}s")
        
        logger.info(f"\nPer-Protocol Details:")
        for metric in all_metrics:
            status = "SUCCESS" if metric.success else "FAILED"
            logger.info(f"  {metric.protocol_name} ({metric.role_name}): {status}")
            logger.info(f"    Time: {metric.execution_time:.2f}s, LLM: {metric.llm_call_count} calls")
        
        logger.info(f"\n{'='*70}")
        logger.info("Running Post-Execution Analysis...")
        logger.info(f"{'='*70}\n")
        run_analysis()
        
        logger.info(f"\n{'='*70}")
        logger.info("Demo 1 Complete!")
        logger.info(f"{'='*70}\n")
        
        return 0
        
    except KeyboardInterrupt:
        logger.error("\nDemo interrupted by user")
        return 1
        
    except Exception as e:
        logger.error(f"Fatal error in demo harness: {e}")
        debug_logger.error(f"Exception: {e}", exc_info=True)
        return 1
        
    finally:
        try:
            debug_logger.debug("Demo harness shutdown")
        except:
            pass


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"Fatal error in demo harness: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
