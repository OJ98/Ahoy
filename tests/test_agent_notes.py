"""Test agent notes persistence module."""

import pytest
import json
import tempfile
from pathlib import Path
from lib.agent_notes import AgentNotes


class TestAgentNotes:
    """Test lightweight agent state persistence."""

    def test_agent_notes_init(self, temp_test_dir):
        """AgentNotes should initialize without error."""
        notes_path = temp_test_dir / "agent_notes.json"
        notes = AgentNotes(notes_path)
        assert notes is not None

    def test_agent_notes_set_get(self, temp_test_dir):
        """AgentNotes should store and retrieve values."""
        notes_path = temp_test_dir / "agent_notes.json"
        notes = AgentNotes(notes_path)
        
        notes.set("test_key", "test_value")
        assert notes.get("test_key") == "test_value"

    def test_agent_notes_persists_to_file(self, temp_test_dir):
        """AgentNotes should persist data to JSON file."""
        notes_path = temp_test_dir / "agent_notes.json"
        notes = AgentNotes(notes_path)
        
        notes.set("key1", "value1")
        notes.save()
        
        # Verify file exists and contains data
        assert notes_path.exists()
        with open(notes_path) as f:
            data = json.load(f)
            assert data.get("key1") == "value1"

    def test_agent_notes_loads_from_file(self, temp_test_dir):
        """AgentNotes should load existing data from file."""
        notes_path = temp_test_dir / "agent_notes.json"
        
        # Create file with data
        data = {"key1": "value1", "key2": "value2"}
        with open(notes_path, "w") as f:
            json.dump(data, f)
        
        # Load it
        notes = AgentNotes(notes_path)
        assert notes.get("key1") == "value1"
        assert notes.get("key2") == "value2"

    def test_agent_notes_delete_key(self, temp_test_dir):
        """AgentNotes should support deleting keys."""
        notes_path = temp_test_dir / "agent_notes.json"
        notes = AgentNotes(notes_path)
        
        notes.set("key1", "value1")
        notes.delete("key1")
        
        assert notes.get("key1") is None

    def test_agent_notes_get_nonexistent_returns_none(self, temp_test_dir):
        """Getting nonexistent key should return None."""
        notes_path = temp_test_dir / "agent_notes.json"
        notes = AgentNotes(notes_path)
        
        result = notes.get("nonexistent_key")
        assert result is None
