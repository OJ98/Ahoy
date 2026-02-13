#!/usr/bin/env python3
"""
Event Simulator: Simulates an external inventory management system.

This module runs in parallel with the agent, injecting inventory alerts
and threshold breaches to demonstrate how external systems can feed into
protocol execution without breaking protocol structure.

The simulator:
1. Waits for the agent to start
2. Injects events at configured intervals
3. Logs all injections for analysis
4. Gracefully shuts down when agent completes

Usage:
    from demo.demo4.event_simulator import InventorySystemSimulator
    sim = InventorySystemSimulator(protocol="Purchase", role="Buyer")
    sim.inject_events()  # Run simulation in background
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.event_injector import post_event_to_agent, get_event_queue_summary


class InventorySystemSimulator:
    """Simulates external inventory management system events."""
    
    def __init__(self, protocol: str, role: str, log_file: Optional[Path] = None):
        """
        Initialize the simulator.
        
        Args:
            protocol: Protocol name (e.g., "Purchase")
            role: Role name (e.g., "Buyer")
            log_file: Optional log file for simulator output
        """
        self.protocol = protocol
        self.role = role
        self.log_file = log_file
        self.events_log = []
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the simulator."""
        logger = logging.getLogger(f"InventorySimulator.{self.role}")
        logger.setLevel(logging.DEBUG)
        logger.handlers = []  # Clear existing handlers
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '[%(asctime)s] [InventorySim] %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
        
        # File handler if specified
        if self.log_file:
            file_handler = logging.FileHandler(self.log_file, mode='a')
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
        
        return logger
    
    async def wait_for_agent_ready(self, timeout: float = 15.0) -> bool:
        """
        Wait for the agent to be ready (event queue file created).
        
        Args:
            timeout: Maximum time to wait in seconds
        
        Returns:
            bool: True if agent ready, False if timeout
        """
        import tempfile
        queue_file = Path(tempfile.gettempdir()) / "maf_events_queue.json"
        
        start_time = time.time()
        check_count = 0
        while time.time() - start_time < timeout:
            # Check if the agent has created the event queue file
            # This indicates the agent is fully initialized and ready for events
            if queue_file.exists():
                elapsed = time.time() - self.start_time
                self.logger.info(f"[+{elapsed:.2f}s] [OK] Agent ready! Event queue file found")
                self.logger.info(f"[+{elapsed:.2f}s]   Queue file: {queue_file}")
                # Verify we can read it
                try:
                    with open(queue_file, 'r') as f:
                        data = json.load(f)
                    self.logger.info(f"[+{elapsed:.2f}s]   Queue file readable, contains {len(data.get('events', []))} events")
                except Exception as e:
                    self.logger.warning(f"[+{elapsed:.2f}s]   Warning: Could not read queue file: {e}")
                return True
            
            check_count += 1
            if check_count % 50 == 0:  # Log every 5 seconds
                elapsed = time.time() - self.start_time
                self.logger.debug(f"[+{elapsed:.2f}s] Still waiting for agent... checking for {queue_file}")
            
            await asyncio.sleep(0.1)
        
        elapsed = time.time() - self.start_time
        self.logger.error(f"[+{elapsed:.2f}s] [FAIL] Timeout waiting for agent (queue file not created after {timeout}s)")
        self.logger.error(f"[+{elapsed:.2f}s]   Expected queue file: {queue_file}")
        return True  # Proceed anyway, agent might still pick up events
    
    def log_event_injection(self, event_type: str, message: str, priority: str, metadata: Dict[str, Any]):
        """Log an event injection for later analysis."""
        self.events_log.append({
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": time.time() - self.start_time,
            "event_type": event_type,
            "message": message,
            "priority": priority,
            "metadata": metadata
        })
    
    async def inject_events(self):
        """
        Inject a single event: Purchase request for a trolley with delivery constraints.
        
        This demonstrates external systems providing context to protocol execution.
        The agent's LLM will see this request when making purchase decisions.
        
        CRITICAL TIMING: Event must be injected BEFORE the agent makes its first
        decisions. Any delay allows the agent to process decisions without the event
        context. We inject immediately after confirming agent readiness.
        """
        self.start_time = time.time()
        self.logger.info(f"Starting purchase event simulator for {self.protocol}.{self.role}")
        
        # Wait for agent to be ready
        if not await self.wait_for_agent_ready():
            self.logger.error("Agent not ready, aborting simulation")
            return
        
        elapsed = time.time() - self.start_time
        self.logger.info(f"[+{elapsed:.2f}s] Agent ready, IMMEDIATELY INJECTING EVENT (no delay!)")
        
        # CRITICAL: Inject event with minimal delay to ensure it's available for initial decisions
        # Even a 100ms delay can cause the agent to make decisions before event is in queue
        # Wait just a tiny bit (100ms) to ensure event queue file is fully written and readable
        await asyncio.sleep(0.1)
        
        # Inject a single event: trolley purchase request
        success = post_event_to_agent(
            event_type="user_defined",
            message="Purchase request: Buy a trolley",
            priority="high",
            metadata={
                "item": "trolley",
                "delivery_address": "123 Main St, Springfield",
                "budget": 29.99
            },
            protocol_name=self.protocol,
            role=self.role
        )
        
        if success:
            elapsed = time.time() - self.start_time
            self.logger.info(f"[+{elapsed:.2f}s] [OK] Injected purchase request: trolley")
            self.logger.info(f"[+{elapsed:.2f}s]   Delivery: 123 Main St, Springfield")
            self.logger.info(f"[+{elapsed:.2f}s]   Budget: $29.99")
            self.log_event_injection(
                "user_defined",
                "Purchase request: Buy a trolley",
                "high",
                {
                    "item": "trolley",
                    "delivery_address": "123 Main St, Springfield",
                    "budget": 29.99
                }
            )
        else:
            elapsed = time.time() - self.start_time
            self.logger.error(f"[+{elapsed:.2f}s] [FAIL] Failed to inject purchase request")
        
        # Wait for agents to process the event and execute protocol
        # (Protocol execution happens asynchronously in the agents)
        elapsed = time.time() - self.start_time
        self.logger.info(f"[+{elapsed:.2f}s] Waiting for protocol execution with injected event...")
        # Give agents enough time to make decisions and execute protocol
        await asyncio.sleep(15)  # Allow agents to fully process event and complete protocol
        
        elapsed = time.time() - self.start_time
        self.logger.info(f"[+{elapsed:.2f}s] [DONE] Event injection simulation complete.")
    
    def get_events_log(self) -> List[Dict[str, Any]]:
        """Get the log of all injected events."""
        return self.events_log.copy()
    
    def save_events_log(self, output_file: Path):
        """Save the events log to a JSON file."""
        try:
            with open(output_file, 'w') as f:
                json.dump({
                    "simulator": {
                        "protocol": self.protocol,
                        "role": self.role,
                        "start_time": datetime.now().isoformat()
                    },
                    "events": self.events_log
                }, f, indent=2)
            self.logger.info(f"Events log saved to {output_file}")
        except Exception as e:
            self.logger.error(f"Failed to save events log: {e}")


# Global simulator instance (used by demo harness)
simulator: Optional[InventorySystemSimulator] = None


async def run_simulator(protocol: str, role: str, log_file: Optional[Path] = None):
    """
    Run the inventory system simulator.
    
    Args:
        protocol: Protocol name
        role: Role name
        log_file: Optional log file path
    """
    global simulator
    simulator = InventorySystemSimulator(protocol, role, log_file)
    await simulator.inject_events()


if __name__ == "__main__":
    # Test the simulator standalone
    async def test():
        await run_simulator("Purchase", "Buyer")
    
    asyncio.run(test())
