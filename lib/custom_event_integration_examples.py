#!/usr/bin/env python3
"""
Example: Adding custom event handling to an agent.

This demonstrates how to use the EventDispatcher in lib/custom_event_handler.py
to add custom business logic events (timeouts, alerts, thresholds) to any agent.

The integration is non-breaking: agents that don't use custom events work exactly
as before. Only agents that explicitly create an event dispatcher enable this feature.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def example_integrate_custom_events_into_buyer_agent():
    """
    Example: How to add custom events to buyer.py
    
    Replace the if __name__ == "__main__": block in buyer.py with:
    """
    
    example_code = """
if __name__ == "__main__":
    # Create event dispatcher BEFORE starting the main agent loop
    event_dispatcher = create_event_dispatcher_for_role("Purchase", "Buyer")
    
    # Schedule business logic events
    scheduler = event_dispatcher.scheduler
    scheduler.schedule_inventory_alert(5.0, "Check inventory status", priority="high")
    scheduler.schedule_timeout_check(15.0, "No purchase progress in 15s")
    scheduler.schedule_custom(25.0, "Market conditions changed", 
                             metadata={"condition": "price_spike"})
    
    # Configure the decision callback (optional, for advanced use)
    # event_dispatcher.set_decision_callback(custom_handler)
    
    # Start the normal buyer agent
    # The event dispatcher runs concurrently with the adapter
    # (no code change needed - handled automatically in ahoy.py)
"""
    
    return example_code


def example_create_custom_agent_with_events():
    """
    Example: Creating a new agent that uses custom events
    """
    
    example_code = '''
#!/usr/bin/env python3
"""Custom agent with event handling."""

import asyncio
from pathlib import Path
from lib.custom_event_handler import (
    EventDispatcher, 
    CustomEventType,
    ConcurrentEventLock
)


class CustomEventAgent:
    """Agent that handles both protocol messages and custom business events."""
    
    def __init__(self, protocol: str, role: str):
        self.protocol = protocol
        self.role = role
        self.event_dispatcher = EventDispatcher()
        self.scheduler = self.event_dispatcher.create_scheduler(role, protocol, role)
    
    def schedule_events(self):
        """Configure custom events for this agent."""
        # Schedule inventory check every 5 seconds
        self.scheduler.schedule_inventory_alert(5.0, "Inventory low", priority="high")
        
        # Schedule timeout check every 10 seconds
        self.scheduler.schedule_timeout_check(10.0, "Protocol stall check")
    
    async def handle_custom_event(self, event):
        """Handle a custom event."""
        print(f"[{self.role}] Received custom event: {event}")
        # Here you would integrate with LLM decision logic
    
    async def run(self):
        """Run agent with event handling."""
        self.schedule_events()
        self.scheduler.set_event_callback(self.handle_custom_event)
        
        # Start event scheduler
        await self.scheduler.start()


async def main():
    """Example usage."""
    agent = CustomEventAgent("Purchase", "Buyer")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
'''
    
    return example_code


if __name__ == "__main__":
    print("=" * 70)
    print("CUSTOM EVENT HANDLING INTEGRATION EXAMPLES")
    print("=" * 70)
    
    print("\n1. INTEGRATING CUSTOM EVENTS INTO EXISTING AGENT (buyer.py)")
    print("-" * 70)
    print(example_integrate_custom_events_into_buyer_agent())
    
    print("\n2. CREATING NEW CUSTOM EVENT AGENT")
    print("-" * 70)
    print(example_create_custom_agent_with_events())
    
    print("\n3. KEY FILES")
    print("-" * 70)
    print("- lib/custom_event_handler.py: Event scheduling and locking infrastructure")
    print("- agents/ahoy.py: Generic agent with optional event dispatcher support")
    print("- This file: Integration examples and documentation")
    
    print("\n4. HOW IT WORKS")
    print("-" * 70)
    print("""
EventDispatcher (in lib/custom_event_handler.py):
  ├─ CustomEventScheduler: Schedules and fires events on timeline
  ├─ ConcurrentEventLock: Serializes LLM endpoint access (adapter + custom events)
  └─ EventDispatcher: Unifies both event types

Integration with ahoy.py:
  1. call create_event_dispatcher_for_role(protocol, role)
  2. Use dispatcher.scheduler to schedule events
  3. Start the dispatcher - events fire asynchronously
  4. Custom events pass through same decision logic as adapter reactions

Non-Breaking Design:
  ✓ If no event dispatcher created → works like original (backward compatible)
  ✓ If event dispatcher created → runs alongside adapter (concurrent)
  ✓ Minimal changes to ahoy.py (just ~20 lines of optional code)
  ✓ All complexity hidden in lib/custom_event_handler.py
""")
