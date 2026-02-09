#!/usr/bin/env python3
"""
Agent Notes - Lightweight note-taking system for agents.
Agents save important state/memory during execution.
Notes are stored as simple key-value pairs in JSON and reset each run.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class AgentNotes:
    """
    Simplified note-taking system for agents to save important state.
    
    Only records key-value pairs from save_state_to_memory tool calls.
    Notes are NOT persisted across runs - they reset with each execution.
    
    Usage:
        notes = AgentNotes('Buyer')
        notes.save('procurement_constraints', 'Budget: $20.00...')
        notes.get_all()  # Returns {'procurement_constraints': 'Budget: $20.00...'}
    """
    
    def __init__(self, agent_name: str, notes_dir: str = "logs/agent_notes"):
        """
        Initialize the notes system.
        
        Args:
            agent_name: Name of the agent (e.g., 'Buyer', 'Seller', 'Adapter')
            notes_dir: Directory to store JSON note files
        
        Notes do NOT load from previous runs - always start fresh.
        """
        self.agent_name = agent_name
        self.notes_dir = Path(notes_dir)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        
        # Simple key-value store for saved state
        self.data: Dict[str, Any] = {}
        # All agents share the same agent_notes.json file
        self.notes_file = self.notes_dir / "agent_notes.json"
        
        # NOTE: Deliberately NOT loading previous run data - notes reset each run
    
    def save(self, key: str, value: Any) -> None:
        """
        Save a key-value pair to the agent's notes.
        
        This is called when save_state_to_memory tool is executed.
        
        Args:
            key: The key to store (e.g., 'procurement_constraints', 'transaction_strategy')
            value: The value to store (string or any JSON-serializable value)
        """
        self.data[key] = value
        self._save()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a saved value by key.
        
        Args:
            key: The key to retrieve
            default: Value to return if key not found
            
        Returns:
            The saved value or default if not found
        """
        return self.data.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all saved key-value pairs."""
        return self.data.copy()
    
    def clear(self) -> None:
        """
        Clear all saved notes for this run.
        
        Called at startup to ensure fresh notes each execution.
        """
        self.data = {}
        self._delete_file()
    
    def _delete_file(self) -> None:
        """Delete the notes file if it exists."""
        try:
            if self.notes_file.exists():
                self.notes_file.unlink()
        except IOError:
            pass
    
    def _save(self) -> None:
        """Save all notes to JSON file."""
        try:
            # Write all agent data to shared agent_notes.json
            # Load existing file to see all agents' data
            all_agents_data = {}
            if self.notes_file.exists():
                try:
                    with open(self.notes_file, 'r') as f:
                        all_agents_data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    all_agents_data = {}
            
            # Update this agent's data
            all_agents_data[self.agent_name] = self.data
            
            # Write back
            with open(self.notes_file, 'w') as f:
                json.dump(all_agents_data, f, indent=2, default=str)
        except IOError:
            pass


# Global notes instances (per-agent)
_agent_notes: Dict[str, AgentNotes] = {}


def get_agent_notes(agent_name: str) -> AgentNotes:
    """
    Get or create an AgentNotes instance for the specified agent.
    
    This function is the primary API for agents to access their notes.
    Notes do NOT persist across runs - calling this creates a fresh instance.
    
    Args:
        agent_name: Name of the agent (e.g., 'Buyer', 'Seller', 'Adapter')
        
    Returns:
        AgentNotes instance for that agent
    
    Example:
        notes = get_agent_notes('Buyer')
        notes.save('budget_constraint', '$20.00')
        notes.get('budget_constraint')  # Returns '$20.00'
    """
    if agent_name not in _agent_notes:
        _agent_notes[agent_name] = AgentNotes(agent_name)
    return _agent_notes[agent_name]


# Backward compatibility alias
def get_agent_notes_tracker(agent_name: str) -> AgentNotes:
    """Backward compatibility. Use get_agent_notes() instead."""
    return get_agent_notes(agent_name)


def reset_agent_notes(agent_name: str) -> None:
    """
    Reset the notes for an agent.
    
    Clears the in-memory data and deletes the notes file for that agent.
    Call this at startup to ensure fresh notes each run.
    """
    if agent_name in _agent_notes:
        _agent_notes[agent_name].clear()
        del _agent_notes[agent_name]

