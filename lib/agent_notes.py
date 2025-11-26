#!/usr/bin/env python3
"""
Agent Notes - Microsoft Agent Framework inspired note-taking system
Allows agents to call note() function to record arbitrary information in structured format.
Notes are stored as JSON for easy retrieval and analysis.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class AgentNotes:
    """
    General-purpose note-taking system for agents.
    
    Agents can call note() to record any information they want to track.
    Notes are automatically timestamped and saved to JSON files.
    
    Usage:
        notes = AgentNotes('Buyer')
        notes.note('observation', {'type': 'price_comparison', 'vendor_a': 10, 'vendor_b': 12})
        notes.note('decision', {'action': 'accept', 'reason': 'best_value', 'vendor': 'vendor_a'})
        notes.note('action', {'sent_message': 'rfq', 'id': 'RFQ_001', 'item': 'pen'})
    """
    
    def __init__(self, agent_name: str, notes_dir: str = "logs/agent_notes"):
        """
        Initialize the notes system.
        
        Args:
            agent_name: Name of the agent (e.g., 'Buyer', 'Seller', 'Shipper')
            notes_dir: Directory to store JSON note files
        """
        self.agent_name = agent_name
        self.notes_dir = Path(notes_dir)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        
        # All notes stored in a single list with type/category field
        self.entries: List[Dict[str, Any]] = []
        self.notes_file = self.notes_dir / f"{agent_name.lower()}_notes.json"
        
        # Load existing notes if they exist
        self._load()
    
    def note(self, note_type: str, data: Dict[str, Any] = None, **kwargs) -> None:
        """
        Record a note of any type.
        
        This is the primary method agents use to track information.
        Notes are automatically timestamped and persisted to JSON.
        
        Args:
            note_type: Type/category of note (e.g., 'rfq', 'observation', 'decision', 'action', etc.)
                      Agents can define their own types as needed
            data: Dictionary containing the note content
            **kwargs: Alternative way to pass note content as keyword arguments
        
        Examples:
            # Using data dict
            notes.note('action', {'sent': 'rfq', 'id': 'RFQ_001'})
            
            # Using kwargs
            notes.note('decision', action='accept', reason='best_price', score=9.5)
            
            # Mixed
            notes.note('observation', {'comparison': 'vendors'}, a=10, b=12)
        """
        # Merge data dict and kwargs
        note_content = data.copy() if data else {}
        note_content.update(kwargs)
        
        # Create entry with automatic timestamp
        entry = {
            'timestamp': datetime.now().isoformat(),
            'type': note_type,
            'data': note_content
        }
        
        self.entries.append(entry)
        self._save()
    
    def note_message(self, message_type: str, **kwargs) -> None:
        """
        Convenience method to note protocol messages.
        
        Args:
            message_type: Type of message (rfq, quote, accept, reject, deliver, completed, etc.)
            **kwargs: Message parameters (ID, item, price, reason, etc.)
        """
        self.note('message', {'type': message_type, **kwargs})
    
    def note_decision(self, decision: str, **details) -> None:
        """
        Convenience method to note a decision made by the agent.
        
        Args:
            decision: What decision was made (e.g., 'accept_quote', 'reject_offer', 'complete_transaction')
            **details: Additional decision details (reason, criteria, score, etc.)
        """
        self.note('decision', {'action': decision, **details})
    
    def note_observation(self, observation: str, **details) -> None:
        """
        Convenience method to note an observation about the protocol or market.
        
        Args:
            observation: What was observed (e.g., 'price_increase', 'supplier_unavailable', 'delivery_delay')
            **details: Additional observation details (values, timing, impact, etc.)
        """
        self.note('observation', {'what': observation, **details})
    
    def get_all_notes(self) -> List[Dict[str, Any]]:
        """Get all notes in chronological order."""
        return self.entries.copy()
    
    def get_notes_by_type(self, note_type: str) -> List[Dict[str, Any]]:
        """Get all notes of a specific type."""
        return [e for e in self.entries if e['type'] == note_type]
    
    def get_latest_notes(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent N notes."""
        return self.entries[-count:] if self.entries else []
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all notes.
        
        Returns:
            Dictionary with summary information
        """
        note_types = {}
        for entry in self.entries:
            note_type = entry['type']
            note_types[note_type] = note_types.get(note_type, 0) + 1
        
        return {
            'agent': self.agent_name,
            'total_notes': len(self.entries),
            'note_types': note_types,
            'timestamp': datetime.now().isoformat()
        }
    
    def _load(self) -> None:
        """Load notes from JSON file if it exists."""
        if self.notes_file.exists():
            try:
                with open(self.notes_file, 'r') as f:
                    data = json.load(f)
                    self.entries = data.get('entries', [])
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load notes from {self.notes_file}: {e}")
                self.entries = []
        else:
            self.entries = []
    
    def _save(self) -> None:
        """Save notes to JSON file."""
        try:
            data = {
                'agent': self.agent_name,
                'last_updated': datetime.now().isoformat(),
                'entries': self.entries
            }
            
            with open(self.notes_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except IOError as e:
            print(f"Warning: Could not save notes to {self.notes_file}: {e}")
    
    def clear_all(self) -> None:
        """Clear all notes."""
        self.entries = []
        self._save()
    
    def export(self, filepath: str) -> None:
        """
        Export all notes to a specified JSON file.
        
        Args:
            filepath: Path to export the notes to
        """
        try:
            export_data = {
                'agent': self.agent_name,
                'export_time': datetime.now().isoformat(),
                'summary': self.get_summary(),
                'entries': self.entries
            }
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
        except IOError as e:
            print(f"Error: Could not export notes to {filepath}: {e}")


# Global notes instances (per-agent)
_agent_notes: Dict[str, AgentNotes] = {}


def get_agent_notes(agent_name: str) -> AgentNotes:
    """
    Get or create an AgentNotes instance for the specified agent.
    
    This function is the primary API for agents to access their notes.
    
    Args:
        agent_name: Name of the agent (e.g., 'Buyer', 'Seller', 'Shipper')
        
    Returns:
        AgentNotes instance for that agent
    
    Example:
        notes = get_agent_notes('Buyer')
        notes.note('rfq', {'id': 'RFQ_001', 'item': 'pen'})
        notes.note_decision('accept_quote', reason='best_price', vendor='A')
    """
    if agent_name not in _agent_notes:
        _agent_notes[agent_name] = AgentNotes(agent_name)
    return _agent_notes[agent_name]


# Backward compatibility alias
def get_agent_notes_tracker(agent_name: str) -> AgentNotes:
    """Backward compatibility. Use get_agent_notes() instead."""
    return get_agent_notes(agent_name)


def reset_agent_notes(agent_name: str) -> None:
    """Reset the notes for an agent."""
    if agent_name in _agent_notes:
        del _agent_notes[agent_name]
