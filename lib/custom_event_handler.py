#!/usr/bin/env python3
"""
Custom Event Handler: Queue-based event system for protocol agents.

Agents can post custom events to a local queue, and check the queue
during their main loop to process custom events.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Any


class CustomEventType(Enum):
    """Types of custom business logic events."""
    INVENTORY_ALERT = "inventory_alert"
    TIMEOUT_CHECK = "timeout_check"
    THRESHOLD_BREACH = "threshold_breach"
    STALL_DETECTION = "stall_detection"
    USER_DEFINED = "user_defined"


@dataclass
class CustomEvent:
    """Represents a custom business logic event."""
    event_type: CustomEventType
    timestamp: float
    description: str
    metadata: Optional[dict] = None

    def __str__(self):
        return f"[{self.event_type.value}] {self.description}"


class EventQueue:
    """
    Simple FIFO queue for custom events.
    
    Agents can post events to the queue, and check it periodically
    during their main decision loop.
    """

    def __init__(self, protocol: str, role: str):
        """Initialize the event queue."""
        self.protocol = protocol
        self.role = role
        self.queue: list = []
        self.processed_count = 0
        self.fired_count = 0

    def post_event(self, event: CustomEvent):
        """Post an event to the queue."""
        self.queue.append(event)

    def post_inventory_alert(self, message: str, priority: str = "normal"):
        """Post an inventory alert event."""
        event = CustomEvent(
            event_type=CustomEventType.INVENTORY_ALERT,
            timestamp=datetime.now().timestamp(),
            description=f"[{priority.upper()}] Inventory: {message}",
            metadata={"priority": priority, "message": message}
        )
        self.post_event(event)

    def has_events(self) -> bool:
        """Check if there are pending events."""
        return len(self.queue) > 0

    def get_next_event(self) -> Optional[CustomEvent]:
        """Get the next event from the queue (FIFO)."""
        if self.queue:
            event = self.queue.pop(0)
            self.processed_count += 1
            return event
        return None

    def peek_events(self) -> list:
        """Get all pending events without removing them."""
        return self.queue.copy()

    def get_summary(self) -> dict:
        """Get summary of event queue."""
        return {
            "protocol": self.protocol,
            "role": self.role,
            "pending_count": len(self.queue),
            "processed_count": self.processed_count,
            "fired_count": self.fired_count,
            "total_events": self.processed_count + self.fired_count
        }


# Global event queue (one per agent instance)
event_queue: Optional[EventQueue] = None
