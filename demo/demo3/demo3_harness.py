#!/usr/bin/env python3
"""
Demo 3 Harness: Concurrent Multi-Protocol Participation (Single Agent, Multiple Roles)
ONE agent simultaneously plays roles in BOTH Purchase and Logistics protocols.

This tests true concurrent multiprotocol participation by having a single agent
handle two different protocol contexts in parallel, demonstrating protocol-agnostic
agent coordination.

Flow:
1. Configure ahoy.py for MULTIPLE roles: Purchase:Buyer + Logistics:Merchant
2. Start supporting agents for both protocols
3. Start ONE ahoy.py that handles both roles concurrently
4. Monitor until both protocols complete
5. Analyze multiprotocol performance metrics
"""

import asyncio
import json
import logging
import subprocess
import sys
import tempfile
import time
import os
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

# Add project root to path
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
DEMO_LOG_FILE = DEMO_RESULTS_DIR / f"demo3_{RUN_TIMESTAMP}.log"

# Multiprotocol configuration: ONE agent plays multiple roles
ROLES_TO_PLAY = [
    ("Purchase", "Buyer"),      # Role 1: Buyer in Purchase protocol
    ("Logistics", "Merchant"),   # Role 2: Merchant in Logistics protocol
]

# All supporting agents needed for both protocols
SUPPORTING_AGENTS = {
    "Purchase": ["seller.py", "shipper.py"],
    "Logistics": ["packer.py", "labeler.py", "wrapper.py"]
}

# Input files for scenario context
INPUT_FILES = {
    "Purchase": PROJECT_ROOT / "input_purchase.txt",
    "Logistics": PROJECT_ROOT / "input_logistics.txt"
}

# Global logging and metrics setup
logger: Optional[logging.Logger] = None
debug_logger: Optional[logging.Logger] = None
all_metrics: List[Any] = []


# ============================================================================
# DATA STRUCTURES
# ============================================================================

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


@dataclass
class ConcurrentMetrics:
    """Aggregated metrics for concurrent multiprotocol execution."""
    run_timestamp: str
    execution_mode: str = "concurrent"
    total_execution_time: float = 0
    protocols_completed: int = 0
    total_llm_calls: int = 0
    total_llm_duration: float = 0
    time_saved_vs_sequential: float = 0


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Configure detailed logging for demo execution."""
    global logger, debug_logger
    
    # Create loggers
    debug_logger = logging.getLogger("demo3_debug")
    logger = logging.getLogger("demo3")
    
    # Set level
    debug_logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
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
    
    # Console handler (info level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    logger.addHandler(debug_handler)
    
    return debug_logger, logger


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

def write_multiprotocol_ahoy_config(roles: List[Tuple[str, str]], input_files: Dict[str, Path]) -> None:
    """
    Write ahoy.py configuration for multiple roles across protocols.
    Specifies explicit agent identity in JSON config.
    """
    config_file = Path(tempfile.gettempdir()) / "maf_chips_config.txt"
    
    # Build JSON format with explicit agent identity 
    roles_list = [{"protocol": protocol, "role": role} for protocol, role in roles]
    config_data = {
        "agent": "ahoy",  # Explicit agent identity for multiprotocol scenarios
        "roles": roles_list
    }
    config_content = json.dumps(config_data)
    
    try:
        config_file.write_text(config_content)
        debug_logger.debug(f"Wrote multiprotocol ahoy config: {config_content}")
        
        # Write combined input file
        input_txt = PROJECT_ROOT / "input.txt"
        combined_input = ""
        for protocol, role in roles:
            if protocol in input_files and input_files[protocol].exists():
                combined_input += f"=== {protocol} Protocol ({role}) ===\n"
                combined_input += input_files[protocol].read_text()
                combined_input += "\n\n"
        
        if combined_input:
            input_txt.write_text(combined_input)
            debug_logger.debug(f"Wrote combined scenario input")
        
    except Exception as e:
        debug_logger.error(f"Failed to write multiprotocol config: {e}")
        raise


def clear_ahoy_config() -> None:
    """Clear ahoy.py configuration."""
    config_file = Path(tempfile.gettempdir()) / "maf_chips_config.txt"
    if config_file.exists():
        try:
            config_file.unlink()
            debug_logger.debug("Cleared config file")
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
            debug_logger.debug("Cleared stop signal")
        except Exception as e:
            debug_logger.warning(f"Failed to clear stop signal: {e}")


def set_stop_signal():
    """Set the stop signal to terminate agents."""
    stop_path = get_stop_signal_path()
    try:
        stop_path.write_text("STOP")
        debug_logger.debug("Set stop signal")
    except Exception as e:
        debug_logger.error(f"Failed to set stop signal: {e}")


# ============================================================================
# AGENT MANAGEMENT
# ============================================================================

def start_multiprotocol_ahoy_agent(roles: List[Tuple[str, str]], input_files: Dict[str, Path]) -> subprocess.Popen:
    """Start ONE ahoy.py agent configured to play multiple roles across protocols."""
    write_multiprotocol_ahoy_config(roles, input_files)
    
    ahoy_script = PROJECT_ROOT / "agents" / "ahoy.py"
    if not ahoy_script.exists():
        raise FileNotFoundError(f"ahoy.py not found at {ahoy_script}")
    
    try:
        process = subprocess.Popen(
            [sys.executable, str(ahoy_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        roles_str = ", ".join([f"{r}({p})" for p, r in roles])
        debug_logger.debug(f"Started ahoy.py (PID {process.pid}) for multiprotocol: {roles_str}")
        return process
    except Exception as e:
        debug_logger.error(f"Failed to start ahoy.py: {e}")
        raise


def start_supporting_agents(protocols: List[str], ahoy_roles: List[Tuple[str, str]] = None) -> List[subprocess.Popen]:
    """Start supporting agents for non-ahoy roles only.
    
    Skips starting agents for roles that ahoy is playing. Sets MULTIPROTOCOL_AHOY_ROLES
    environment variable so message routing goes to ahoy's port (8000).
    """
    processes = []
    
    # Build set of roles that ahoy is playing
    ahoy_role_set = set()
    if ahoy_roles:
        ahoy_role_set = {role_name.lower() for _, role_name in ahoy_roles}
    
    # Set environment variable to enable multiprotocol override in configuration
    env = os.environ.copy()
    if ahoy_roles:
        # Format: "Protocol1:Role1,Protocol2:Role2"
        roles_str = ",".join([f"{p}:{r}" for p, r in ahoy_roles])
        env["MULTIPROTOCOL_AHOY_ROLES"] = roles_str
        debug_logger.debug(f"Set MULTIPROTOCOL_AHOY_ROLES={roles_str}")
    
    # Map agent script names to their roles for filtering
    script_to_role = {
        "buyer.py": "buyer",
        "seller.py": "seller",
        "shipper.py": "shipper",
        "merchant.py": "merchant",
        "wrapper.py": "wrapper",
        "labeler.py": "labeler",
        "packer.py": "packer",
    }
    
    for protocol in protocols:
        agent_scripts = SUPPORTING_AGENTS.get(protocol, [])
        for script_name in agent_scripts:
            # Skip if this role is being played by ahoy
            script_role = script_to_role.get(script_name, "").lower()
            if script_role in ahoy_role_set:
                debug_logger.debug(f"Skipping {script_name} - ahoy is playing {script_role}")
                continue
            
            agent_script = PROJECT_ROOT / "agents" / script_name
            if not agent_script.exists():
                debug_logger.warning(f"Agent script not found: {agent_script}")
                continue
            
            try:
                process = subprocess.Popen(
                    [sys.executable, str(agent_script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    env=env  # Pass environment with MULTIPROTOCOL_AHOY_ROLES
                )
                processes.append(process)
                debug_logger.debug(f"Started {script_name} (PID {process.pid}) for {protocol}")
            except Exception as e:
                debug_logger.error(f"Failed to start {script_name}: {e}")
    
    return processes


def start_ahoy_agent(protocol_name: str, role_name: str, input_file: Optional[Path] = None) -> subprocess.Popen:
    """Start ahoy.py agent for a specific protocol and role."""
    write_multiprotocol_ahoy_config([(protocol_name, role_name)], {protocol_name: input_file})
    
    ahoy_script = PROJECT_ROOT / "agents" / "ahoy.py"
    if not ahoy_script.exists():
        raise FileNotFoundError(f"ahoy.py not found at {ahoy_script}")
    
    try:
        process = subprocess.Popen(
            [sys.executable, str(ahoy_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        debug_logger.debug(f"Started ahoy.py (PID {process.pid}) for {protocol_name}:{role_name}")
        return process
    except Exception as e:
        debug_logger.error(f"Failed to start ahoy.py: {e}")
        raise


def start_other_agents(protocol_name: str, agent_scripts: List[str]) -> List[subprocess.Popen]:
    """Start supporting agent scripts for a protocol."""
    processes = []
    
    for script_name in agent_scripts:
        agent_script = PROJECT_ROOT / "agents" / script_name
        if not agent_script.exists():
            debug_logger.warning(f"Agent script not found: {agent_script}")
            continue
        
        try:
            process = subprocess.Popen(
                [sys.executable, str(agent_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            processes.append(process)
            debug_logger.debug(f"Started {script_name} (PID {process.pid}) for {protocol_name}")
        except Exception as e:
            debug_logger.error(f"Failed to start {script_name}: {e}")
    
    return processes


def terminate_agent(process: subprocess.Popen):
    """Terminate a single agent process."""
    try:
        process.terminate()
        process.wait(timeout=5)
        debug_logger.debug(f"Terminated agent process {process.pid}")
    except subprocess.TimeoutExpired:
        process.kill()
        debug_logger.debug(f"Killed agent process {process.pid}")
    except Exception as e:
        debug_logger.warning(f"Error terminating process: {e}")


def terminate_agents(processes: List[subprocess.Popen]):
    """Terminate multiple agent processes."""
    for process in processes:
        terminate_agent(process)


def append_agent_log_to_demo_log(protocol_name: str, role_name: str):
    """Append agent's detailed log to the demo log file."""
    # ahoy.py creates timestamped logs: generic_agent_debug_*.log
    # But also check for role-specific logs from hardcoded agents
    agent_log = None
    
    # First, try to find the most recent generic_agent_debug_*.log
    debug_logs = list(LOG_DIR.glob("generic_agent_debug_*.log"))
    if debug_logs:
        agent_log = max(debug_logs, key=lambda p: p.stat().st_mtime)
    
    # Fallback to role-specific log
    if not agent_log:
        agent_log = LOG_DIR / f"{role_name.lower()}.log"
    
    if not agent_log or not agent_log.exists():
        debug_logger.debug(f"Agent log not found for {role_name}")
        return
    
    try:
        with open(agent_log, 'r', encoding='utf-8', errors='ignore') as af:
            agent_content = af.read()
        
        with open(DEMO_LOG_FILE, 'a', encoding='utf-8', errors='ignore') as df:
            df.write(f"\n{'='*70}\n")
            df.write(f"Agent Log: {protocol_name} - {role_name}\n")
            df.write(f"Source: {agent_log.name}\n")
            df.write(f"{'='*70}\n")
            df.write(agent_content)
            df.write(f"\n{'='*70}\n")
        
        debug_logger.debug(f"Appended agent log for {role_name} from {agent_log.name}")
    except Exception as e:
        debug_logger.warning(f"Failed to append agent log: {e}")


def get_latest_agent_log() -> Optional[Path]:
    """Get the latest agent log file."""
    agent_logs = list(LOG_DIR.glob("*.log"))
    if agent_logs:
        return max(agent_logs, key=lambda p: p.stat().st_mtime)
    return None


def count_llm_calls_from_log(agent_log: Optional[Path]) -> int:
    """Count LLM calls from agent log file."""
    if not agent_log:
        # If no specific log provided, count from all generic_agent_debug logs created recently
        debug_logs = list(LOG_DIR.glob("generic_agent_debug_*.log"))
        if not debug_logs:
            return 0
        
        # Get ALL debug logs from this session - count total RAW LLM RESPONSE entries
        total_calls = 0
        for log_file in debug_logs:
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Count both markers that indicate an LLM decision was made
                    total_calls += content.count('[DEBUG] - =================================================================================\nRAW LLM RESPONSE')
                    # Also count if the marker appears differently
                    if 'RAW LLM RESPONSE' in content:
                        # Count all occurrences of the section header
                        raw_count = content.count('RAW LLM RESPONSE')
                        total_calls = max(total_calls, raw_count)
            except Exception as e:
                debug_logger.warning(f"Failed to read log {log_file.name}: {e}")
        
        return total_calls
    
    if not agent_log.exists():
        return 0
    
    try:
        with open(agent_log, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            return content.count('RAW LLM RESPONSE')
    except Exception as e:
        debug_logger.warning(f"Failed to count LLM calls: {e}")
        return 0


def check_execution_success(agent_log: Optional[Path]) -> bool:
    """Check if protocol execution was successful."""
    if not agent_log:
        # Check all generic_agent_debug logs
        debug_logs = list(LOG_DIR.glob("generic_agent_debug_*.log"))
        if not debug_logs:
            return False
        
        for log_file in sorted(debug_logs, key=lambda p: p.stat().st_mtime, reverse=True)[:2]:
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if any(indicator in content for indicator in [
                        "Sending message:",
                        "RAW LLM RESPONSE"
                    ]):
                        return True
            except Exception as e:
                debug_logger.warning(f"Failed to check success: {e}")
        
        return False
    
    if not agent_log.exists():
        return False
    
    try:
        with open(agent_log, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            return any(indicator in content for indicator in [
                "Sending message:",
                "RAW LLM RESPONSE"
            ])
    except Exception as e:
        debug_logger.warning(f"Failed to check success: {e}")
        return False


# ============================================================================
# CONCURRENT PROTOCOL EXECUTION
# ============================================================================

async def execute_protocol_concurrent(
    protocol_name: str, 
    role_name: str,
    other_agents: List[str],
    input_file: Path,
    max_wait_time: float = 120
) -> Tuple[subprocess.Popen, List[subprocess.Popen], ProtocolMetrics]:
    """
    Start execution of a protocol and return processes for concurrent monitoring.
    """
    start_time = time.time()
    ahoy_process = None
    other_processes = []
    
    try:
        # Start other agents first
        other_processes = start_other_agents(protocol_name, other_agents)
        debug_logger.debug(f"Started {len(other_processes)} supporting agents for {protocol_name}")
        
        # Then start ahoy.py agent
        ahoy_process = start_ahoy_agent(protocol_name, role_name, input_file)
        
        logger.info(f"{protocol_name} protocol started (role: {role_name})")
        
        # Return processes for concurrent monitoring
        return ahoy_process, other_processes, None
        
    except Exception as e:
        logger.error(f"Error starting {protocol_name} protocol: {e}")
        debug_logger.error(f"Exception: {e}", exc_info=True)
        raise


async def monitor_concurrent_protocols(
    protocol_processes: Dict[str, Tuple[subprocess.Popen, List[subprocess.Popen]]],
    max_wait_time: float = 120
) -> Dict[str, ProtocolMetrics]:
    """
    Monitor both protocols executing concurrently until completion.
    """
    logger.info(f"Monitoring {len(protocol_processes)} protocols concurrently...")
    
    start_time = time.time()
    protocol_metrics = {}
    completed_protocols = set()
    
    try:
        while time.time() - start_time < max_wait_time:
            await asyncio.sleep(1)
            
            for protocol_name, (ahoy_process, other_processes) in protocol_processes.items():
                if protocol_name in completed_protocols:
                    continue
                
                # Check if ahoy process has exited
                if ahoy_process.poll() is not None:
                    execution_time = time.time() - start_time
                    
                    # Append logs
                    config = PROTOCOL_CONFIGS[protocol_name]
                    append_agent_log_to_demo_log(protocol_name, config["ahoy_role"])
                    
                    await asyncio.sleep(0.5)
                    
                    # Collect metrics - count from all debug logs
                    llm_call_count = count_llm_calls_from_log(None)
                    execution_successful = check_execution_success(None)
                    
                    protocol_metrics[protocol_name] = ProtocolMetrics(
                        protocol_name=protocol_name,
                        role_name=config["ahoy_role"],
                        execution_time=execution_time,
                        llm_call_count=llm_call_count,
                        llm_duration_seconds=execution_time,
                        success=execution_successful
                    )
                    
                    completed_protocols.add(protocol_name)
                    logger.info(f"{protocol_name} protocol completed")
                    logger.info(f"  Time: {execution_time:.2f}s, LLM Calls: {llm_call_count}")
            
            # Check if all protocols completed
            if len(completed_protocols) == len(protocol_processes):
                break
        
        # Timeout handling
        if len(completed_protocols) < len(protocol_processes):
            logger.warning(f"Timeout: {len(protocol_processes) - len(completed_protocols)} protocols did not complete")
            set_stop_signal()
            
            # Collect partial metrics for remaining protocols
            for protocol_name, (ahoy_process, _) in protocol_processes.items():
                if protocol_name not in completed_protocols:
                    execution_time = time.time() - start_time
                    config = PROTOCOL_CONFIGS[protocol_name]
                    protocol_metrics[protocol_name] = ProtocolMetrics(
                        protocol_name=protocol_name,
                        role_name=config["ahoy_role"],
                        execution_time=execution_time,
                        llm_call_count=0,
                        llm_duration_seconds=execution_time,
                        success=False,
                        error_message="Timeout"
                    )
        
        return protocol_metrics
        
    except Exception as e:
        logger.error(f"Error monitoring protocols: {e}")
        debug_logger.error(f"Exception: {e}", exc_info=True)
        set_stop_signal()
        raise


def run_analysis():
    """Run the analysis script on demo results."""
    analysis_script = Path(__file__).resolve().parent / "demo3_analysis.py"
    if not analysis_script.exists():
        logger.warning(f"Analysis script not found: {analysis_script}")
        return
    
    try:
        logger.info(f"Executing: {analysis_script.name}")
        debug_logger.debug(f"Full path: {analysis_script}")
        
        # Create metrics data for analysis
        metrics_data = {
            "run_timestamp": RUN_TIMESTAMP,
            "execution_mode": "concurrent",
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
        
        # Clean up
        try:
            Path(temp_metrics_file).unlink()
        except:
            pass
            
    except subprocess.TimeoutExpired:
        logger.warning("Analysis script timed out")
    except Exception as e:
        logger.warning(f"Failed to run analysis: {e}")
        debug_logger.debug(f"Error: {e}", exc_info=True)


# ============================================================================
# MAIN DEMO HARNESS
# ============================================================================

async def main():
    """Main demo3 harness: Single agent with multiple roles across protocols."""
    global logger, debug_logger, all_metrics
    
    # Setup logging
    debug_logger, logger = setup_logging()
    
    logger.info("="*70)
    logger.info("DEMO 3: Concurrent Multi-Protocol Participation")
    logger.info("="*70)
    logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Results Directory: {DEMO_RESULTS_DIR}")
    logger.info(f"Log File: {DEMO_LOG_FILE}")
    debug_logger.debug(f"Project Root: {PROJECT_ROOT}")
    
    all_metrics = []
    
    try:
        # Clear previous state
        clear_stop_signal()
        
        logger.info("\n" + "="*70)
        logger.info("Configuration: One Agent, Multiple Protocol Roles")
        logger.info("="*70 + "\n")
        
        protocols_involved = list(set(p for p, r in ROLES_TO_PLAY))
        
        logger.info(f"Agent will play {len(ROLES_TO_PLAY)} roles across {len(protocols_involved)} protocols:")
        for protocol, role in ROLES_TO_PLAY:
            logger.info(f"  - {role} in {protocol}")
        logger.info("")
        
        # Start supporting agents for all protocols
        logger.info("="*70)
        logger.info("Starting Supporting Agents")
        logger.info("="*70 + "\n")
        
        supporting_processes = start_supporting_agents(protocols_involved, ahoy_roles=ROLES_TO_PLAY)
        logger.info(f"Started {len(supporting_processes)} supporting agents")
        logger.info("")
        
        await asyncio.sleep(1)  # Give them time to start
        
        # Start the multiprotocol ahoy agent
        logger.info("="*70)
        logger.info("Starting Multiprotocol Agent (ahoy.py)")
        logger.info("="*70 + "\n")
        
        start_time = time.time()
        ahoy_process = start_multiprotocol_ahoy_agent(ROLES_TO_PLAY, INPUT_FILES)
        logger.info("Multiprotocol agent started. Waiting for protocol completion...")
        logger.info("")
        
        # Monitor until completion or timeout
        max_wait_time = 120
        elapsed = 0
        poll_interval = 1
        protocol_complete = False
        
        while elapsed < max_wait_time:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            
            # Check if ahoy process has exited
            if ahoy_process.poll() is not None:
                protocol_complete = True
                execution_time = time.time() - start_time
                logger.info(f"Multiprotocol execution completed in {execution_time:.2f}s")
                break
        
        execution_time = time.time() - start_time
        
        if not protocol_complete:
            logger.warning(f"Protocols did not complete within {max_wait_time}s, terminating...")
            set_stop_signal()
            await asyncio.sleep(1)
        
        # Collect metrics
        llm_call_count = count_llm_calls_from_log(None)
        execution_successful = check_execution_success(None)
        
        # Create metrics for each role
        for protocol, role in ROLES_TO_PLAY:
            all_metrics.append(ProtocolMetrics(
                protocol_name=protocol,
                role_name=role,
                execution_time=execution_time,
                llm_call_count=llm_call_count,
                llm_duration_seconds=execution_time,
                success=execution_successful
            ))
        
        logger.info(f"\n{'='*70}")
        logger.info("Execution Metrics")
        logger.info(f"{'='*70}")
        logger.info("")
        logger.info(f"Total Execution Time: {execution_time:.2f}s")
        logger.info(f"LLM Calls: {llm_call_count}")
        logger.info(f"Success: {execution_successful}")
        logger.info("")
        
        # Terminate all agents
        logger.info("")
        logger.info("Terminating agents...")
        set_stop_signal()
        terminate_agent(ahoy_process)
        terminate_agents(supporting_processes)
        logger.info("All agents terminated.")
        logger.info("")
        
        # Save results
        logger.info(f"{'='*70}")
        logger.info("Saving Results")
        logger.info(f"{'='*70}\n")
        
        with open(DEMO_LOG_FILE, 'a', encoding='utf-8', errors='ignore') as f:
            f.write(f"\n\n{'='*70}\n")
            f.write(f"DEMO 3 EXECUTION COMPLETE\n")
            f.write(f"Run Timestamp: {RUN_TIMESTAMP}\n")
            f.write(f"Execution Mode: CONCURRENT MULTIPROTOCOL (Single Agent)\n")
            f.write(f"Total Execution Time: {execution_time:.2f}s\n")
            f.write(f"Protocols: {len(protocols_involved)}\n")
            f.write(f"Roles: {len(ROLES_TO_PLAY)}\n")
            f.write(f"LLM Calls: {llm_call_count}\n")
            f.write(f"Success: {execution_successful}\n")
            f.write(f"{'='*70}\n\n")
        
        logger.info(f"Log saved to: {DEMO_LOG_FILE}")
        
        # Print summary
        logger.info(f"\n{'='*70}")
        logger.info("DEMO 3 SUMMARY - CONCURRENT MULTIPROTOCOL PARTICIPATION")
        logger.info(f"{'='*70}")
        logger.info("")
        logger.info(f"Execution Mode: Single agent playing {len(ROLES_TO_PLAY)} roles across {len(protocols_involved)} protocols")
        logger.info(f"Total Execution Time: {execution_time:.2f}s")
        logger.info(f"LLM Calls: {llm_call_count}")
        logger.info(f"Success: {execution_successful}")
        
        logger.info(f"")
        logger.info(f"Roles Played (Concurrently):")
        for protocol, role in ROLES_TO_PLAY:
            logger.info(f"  - {role} ({protocol})")
        
        logger.info(f"")
        logger.info(f"{'='*70}")
        logger.info("Running Post-Execution Analysis...")
        logger.info(f"{'='*70}")
        logger.info("")
        run_analysis()
        
        logger.info(f"")
        logger.info(f"{'='*70}")
        logger.info("Demo 3 Complete!")
        logger.info(f"{'='*70}")
        logger.info("")
        
        return 0
        
    except KeyboardInterrupt:
        logger.error("\nDemo interrupted by user")
        set_stop_signal()
        return 1
        
    except Exception as e:
        logger.error(f"Fatal error in demo harness: {e}")
        debug_logger.error(f"Exception: {e}", exc_info=True)
        set_stop_signal()
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
