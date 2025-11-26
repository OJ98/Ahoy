#!/usr/bin/env python3
"""RFQ Tracking module using JSON file approach (Agent Framework pattern)."""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any


class RFQTracker:
    """Track RFQs sent using JSON file persistence."""
    
    def __init__(self, output_dir: str = "./logs"):
        """Initialize RFQ tracker."""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.json_file = os.path.join(output_dir, f"rfq_tracking_{self.timestamp}.json")
        
        self.data = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "timestamp": self.timestamp,
                "tracking_type": "RFQ_TRACKER",
                "version": "1.0"
            },
            "rfqs": [],
            "statistics": {
                "total_rfqs": 0,
                "unique_ids": 0,
                "rejected_rfqs": 0,
                "accepted_rfqs": 0
            },
            "summary": {
                "status": "in_progress",
                "transaction_started": datetime.now().isoformat(),
                "transaction_ended": None
            }
        }
        
        self._rfq_cache = {}
        self._write_to_file()
    
    def add_rfq(self, rfq_id: str, item: str, timestamp: Optional[str] = None, 
                status: str = "sent", context: Optional[Dict] = None) -> bool:
        """Add an RFQ to tracking file."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        if rfq_id in self._rfq_cache:
            existing_rfqs = self._rfq_cache[rfq_id]
            for existing in existing_rfqs:
                if existing["item"] == item:
                    existing["last_seen"] = timestamp
                    existing["occurrences"] = existing.get("occurrences", 1) + 1
                    self._write_to_file()
                    return True
                else:
                    status = "duplicate_error"
        
        rfq_entry = {
            "id": rfq_id,
            "item": item,
            "sent_at": timestamp,
            "status": status,
            "context": context or {},
            "occurrences": 1,
            "last_seen": timestamp
        }
        
        self.data["rfqs"].append(rfq_entry)
        
        if rfq_id not in self._rfq_cache:
            self._rfq_cache[rfq_id] = []
        self._rfq_cache[rfq_id].append(rfq_entry)
        
        self.data["statistics"]["total_rfqs"] += 1
        if status == "accepted":
            self.data["statistics"]["accepted_rfqs"] += 1
        elif status == "rejected":
            self.data["statistics"]["rejected_rfqs"] += 1
        elif status == "duplicate_error":
            self.data["statistics"]["rejected_rfqs"] += 1
        
        self.data["statistics"]["unique_ids"] = len(self._rfq_cache)
        self._write_to_file()
        return True
    
    def get_rfq_history(self, rfq_id: Optional[str] = None) -> List[Dict]:
        """Get RFQ history."""
        if rfq_id is None:
            return self.data["rfqs"]
        return [rfq for rfq in self.data["rfqs"] if rfq["id"] == rfq_id]
    
    def has_rfq_id(self, rfq_id: str) -> bool:
        """Check if an RFQ ID has been used."""
        return rfq_id in self._rfq_cache
    
    def get_duplicate_ids(self) -> List[str]:
        """Get list of RFQ IDs with different parameters."""
        duplicates = []
        for rfq_id, rfqs in self._rfq_cache.items():
            items = set(rfq["item"] for rfq in rfqs)
            if len(items) > 1:
                duplicates.append(rfq_id)
        return duplicates
    
    def mark_transaction_complete(self, success: bool = True, 
                                  completion_message: Optional[str] = None):
        """Mark the transaction as complete."""
        self.data["summary"]["status"] = "completed" if success else "failed"
        self.data["summary"]["transaction_ended"] = datetime.now().isoformat()
        if completion_message:
            self.data["summary"]["completion_message"] = completion_message
        self._write_to_file()
    
    def _write_to_file(self):
        """Write current state to JSON file."""
        try:
            self.data["metadata"]["last_updated"] = datetime.now().isoformat()
            with open(self.json_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error writing RFQ tracking file: {e}")
    
    def get_summary(self) -> Dict:
        """Get summary of RFQ tracking data."""
        return {
            "file": self.json_file,
            "total_rfqs": self.data["statistics"]["total_rfqs"],
            "unique_ids": self.data["statistics"]["unique_ids"],
            "accepted": self.data["statistics"]["accepted_rfqs"],
            "rejected": self.data["statistics"]["rejected_rfqs"],
            "duplicates": self.get_duplicate_ids(),
            "status": self.data["summary"]["status"]
        }
    
    def export_summary(self) -> str:
        """Export summary as formatted string."""
        summary = self.get_summary()
        lines = [
            "=== RFQ TRACKING SUMMARY ===",
            f"Tracking file: {summary['file']}",
            f"Total RFQs sent: {summary['total_rfqs']}",
            f"Unique IDs used: {summary['unique_ids']}",
            f"Accepted: {summary['accepted']}",
            f"Rejected: {summary['rejected']}",
        ]
        
        if summary['duplicates']:
            lines.append(f"Duplicate IDs: {', '.join(summary['duplicates'])}")
        
        return "\n".join(lines)


_rfq_tracker = None


def initialize_rfq_tracker(output_dir: str = "./logs") -> RFQTracker:
    """Initialize the global RFQ tracker."""
    global _rfq_tracker
    _rfq_tracker = RFQTracker(output_dir)
    return _rfq_tracker


def get_rfq_tracker() -> Optional[RFQTracker]:
    """Get the global RFQ tracker instance."""
    return _rfq_tracker


def reset_rfq_tracker():
    """Reset the global RFQ tracker."""
    global _rfq_tracker
    _rfq_tracker = None
