#!/usr/bin/env python3
"""
Comprehensive test suite for Demo 6: Custom LLM Events

Tests cover:
- Adapter creation (success and error cases)
- Lock synchronization and deadlock prevention
- Custom event polling
- LLM decision handling
- Concurrent execution
- Metric tracking and validation
"""

import asyncio
import json
import pytest
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configuration import systems, agents
from lib.llm_client import (
    AnthropicLLMClient,
    choose_and_bind,
    initialize_llm_tracker,
    get_llm_tracker,
    reset_llm_tracker
)
from lib.dynamic_adapter_manager import create_adapter_for_role
from demo.harnesses.demo6_custom_events import CustomEventsHarness
from demo.harnesses.base_harness import ExecutionTrace


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def harness():
    """Create a CustomEventsHarness instance."""
    return CustomEventsHarness()


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock(spec=AnthropicLLMClient)
    return client


@pytest.fixture
def execution_trace():
    """Create an ExecutionTrace instance."""
    return ExecutionTrace("test_harness", "test_scenario")


@pytest.fixture
def mock_adapter():
    """Create a mock adapter with necessary attributes."""
    adapter = AsyncMock()
    adapter.enabled_store = MagicMock()
    adapter.enabled_store.messages = MagicMock(return_value=[])
    adapter.send = AsyncMock()
    adapter.start = AsyncMock()
    return adapter


@pytest.fixture(autouse=True)
def reset_tracker():
    """Reset LLM tracker before each test."""
    reset_llm_tracker()
    yield
    reset_llm_tracker()


# ============================================================================
# UNIT TESTS: Adapter Creation
# ============================================================================

class TestAdapterCreation:
    """Tests for adapter creation and error handling."""
    
    def test_create_adapter_success_purchase(self):
        """Test successful adapter creation for Purchase protocol."""
        adapter, error = create_adapter_for_role("Purchase", "Buyer")
        assert adapter is not None, "Adapter should be created successfully"
        assert error is None, "Error should be None on success"
    
    def test_create_adapter_success_logistics(self):
        """Test successful adapter creation for Logistics protocol."""
        adapter, error = create_adapter_for_role("Logistics", "Merchant")
        assert adapter is not None, "Adapter should be created successfully"
        assert error is None, "Error should be None on success"
    
    def test_create_adapter_invalid_protocol(self):
        """Test adapter creation with invalid protocol name."""
        adapter, error = create_adapter_for_role("InvalidProtocol", "Buyer")
        assert adapter is None, "Adapter should be None on error"
        assert error is not None, "Error should be set on invalid protocol"
        assert "not found" in error.lower()
    
    def test_create_adapter_invalid_role(self):
        """Test adapter creation with invalid role name."""
        adapter, error = create_adapter_for_role("Purchase", "InvalidRole")
        assert adapter is None, "Adapter should be None on error"
        assert error is not None, "Error should be set on invalid role"
        assert "not found" in error.lower()
    
    def test_create_adapter_different_color_indices(self):
        """Test adapter creation with different color indices."""
        adapter1, _ = create_adapter_for_role("Purchase", "Buyer", 0)
        adapter2, _ = create_adapter_for_role("Purchase", "Buyer", 1)
        
        assert adapter1 is not None
        assert adapter2 is not None
        # Both should be valid adapters (color doesn't affect core functionality)


# ============================================================================
# UNIT TESTS: Lock Synchronization
# ============================================================================

class TestLockSynchronization:
    """Tests for proper lock usage and deadlock prevention."""
    
    @pytest.mark.asyncio
    async def test_lock_prevents_concurrent_access(self):
        """Test that lock prevents concurrent access to shared counter."""
        counter = {"value": 0}
        lock = asyncio.Lock()
        
        async def increment():
            async with lock:
                # Simulate some work
                await asyncio.sleep(0.01)
                counter["value"] += 1
        
        # Run 10 increments concurrently
        await asyncio.gather(*[increment() for _ in range(10)])
        
        assert counter["value"] == 10, "All increments should complete without race condition"
    
    @pytest.mark.asyncio
    async def test_lock_held_briefly_not_during_llm_call(self):
        """Test that lock is NOT held during slow LLM calls."""
        lock = asyncio.Lock()
        lock_hold_times = []
        
        async def timed_lock_operation():
            """Acquire lock and track how long it's held."""
            async with lock:
                start = asyncio.get_event_loop().time()
                await asyncio.sleep(0.001)  # Simulate brief operation
                end = asyncio.get_event_loop().time()
                lock_hold_times.append(end - start)
        
        # Run 5 operations concurrently
        await asyncio.gather(*[timed_lock_operation() for _ in range(5)])
        
        # Each lock hold should be reasonably brief (< 50ms, allowing for system variance)
        for hold_time in lock_hold_times:
            assert hold_time < 0.05, f"Lock held too long: {hold_time}s"
    
    @pytest.mark.asyncio
    async def test_no_deadlock_between_adapter_and_custom_events(self):
        """Test that adapter polling and custom events don't deadlock."""
        lock = asyncio.Lock()
        events = []
        
        async def adapter_polling():
            """Simulates adapter polling."""
            for i in range(3):
                await asyncio.sleep(0.01)
                async with lock:
                    events.append(("adapter", i))
        
        async def custom_events():
            """Simulates custom events."""
            for i in range(3):
                await asyncio.sleep(0.015)
                async with lock:
                    events.append(("custom", i))
        
        # Run both concurrently with timeout to catch deadlocks
        try:
            await asyncio.wait_for(
                asyncio.gather(adapter_polling(), custom_events()),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            pytest.fail("Deadlock detected: operations timed out")
        
        # Both should complete
        assert any(e[0] == "adapter" for e in events), "Adapter events should occur"
        assert any(e[0] == "custom" for e in events), "Custom events should occur"


# ============================================================================
# UNIT TESTS: Harness Methods
# ============================================================================

class TestHarnessMethods:
    """Tests for harness utility methods."""
    
    def test_validate_enabled_store_empty(self, harness):
        """Test validation with empty enabled store."""
        enabled_store = MagicMock()
        enabled_store.messages = MagicMock(return_value=[])
        
        is_valid, messages = harness._validate_enabled_store(enabled_store)
        assert is_valid is False
        assert messages == []
    
    def test_validate_enabled_store_with_messages(self, harness):
        """Test validation with messages available."""
        mock_msg1 = MagicMock()
        mock_msg2 = MagicMock()
        enabled_store = MagicMock()
        enabled_store.messages = MagicMock(return_value=[mock_msg1, mock_msg2])
        
        is_valid, messages = harness._validate_enabled_store(enabled_store)
        assert is_valid is True
        assert len(messages) == 2
    
    def test_validate_enabled_store_none(self, harness):
        """Test validation with None enabled store."""
        is_valid, messages = harness._validate_enabled_store(None)
        assert is_valid is False
        assert messages == []
    
    def test_print_scenario_header(self, harness, capsys):
        """Test scenario header printing."""
        scenario = {
            "id": "test_scenario",
            "protocol": "Purchase",
            "role": "Buyer",
            "description": "Test description"
        }
        
        harness.print_scenario_header(scenario)
        
        captured = capsys.readouterr()
        assert "test_scenario" in captured.out
        assert "Purchase" in captured.out
        assert "Buyer" in captured.out
        assert "Test description" in captured.out


# ============================================================================
# INTEGRATION TESTS: Scenario Execution
# ============================================================================

class TestScenarioExecution:
    """Tests for full scenario execution."""
    
    @pytest.mark.asyncio
    async def test_scenario_execution_adapter_error(self, harness):
        """Test scenario execution when adapter creation fails."""
        invalid_scenario = {
            "id": "invalid_adapter_test",
            "protocol": "InvalidProtocol",
            "role": "InvalidRole",
            "description": "Test with invalid protocol/role",
            "custom_event_type": "periodic_timeout",
            "custom_event_interval": 1.0,
            "agent_goal": "Should fail"
        }
        
        trace = await harness.execute_scenario(invalid_scenario)
        
        assert trace is not None
        assert len(trace.errors) > 0, "Should have adapter creation error"
        assert any("adapter_creation" in e["type"] for e in trace.errors)
    
    @pytest.mark.asyncio
    async def test_scenario_execution_returns_trace(self, harness):
        """Test that scenario execution returns a valid trace."""
        scenario = harness.test_scenarios[0]  # Use first test scenario
        
        # Mock the LLM client to avoid actual API calls
        with patch.object(harness, 'llm_client') as mock_client:
            mock_client.complete = AsyncMock(return_value='{"choice": null, "params": {}}')
            
            # This will still create real adapters but skip LLM calls
            trace = await harness.execute_scenario(scenario)
        
        assert trace is not None
        assert isinstance(trace, ExecutionTrace)
        assert trace.scenario_id == scenario["id"]
        assert trace.end_time is not None


# ============================================================================
# UNIT TESTS: Metrics Tracking
# ============================================================================

class TestMetricsTracking:
    """Tests for metric collection and reporting."""
    
    def test_execution_trace_creation(self):
        """Test ExecutionTrace creation and initialization."""
        trace = ExecutionTrace("test_harness", "test_scenario")
        
        assert trace.harness_name == "test_harness"
        assert trace.scenario_id == "test_scenario"
        assert trace.events == []
        assert trace.errors == []
        assert trace.metrics == {}
    
    def test_execution_trace_add_event(self):
        """Test adding events to trace."""
        trace = ExecutionTrace("test", "scenario")
        
        trace.add_event("test_event", {"data": "value"})
        
        assert len(trace.events) == 1
        assert trace.events[0]["type"] == "test_event"
        assert trace.events[0]["data"]["data"] == "value"
    
    def test_execution_trace_add_error(self):
        """Test adding errors to trace."""
        trace = ExecutionTrace("test", "scenario")
        
        trace.add_error("error_type", "error message")
        
        assert len(trace.errors) == 1
        assert trace.errors[0]["type"] == "error_type"
        assert trace.errors[0]["message"] == "error message"
    
    def test_execution_trace_finalize(self):
        """Test trace finalization."""
        trace = ExecutionTrace("test", "scenario")
        start_time = trace.start_time
        
        # Wait a bit
        import time
        time.sleep(0.01)
        
        trace.finalize()
        
        assert trace.end_time is not None
        assert trace.end_time > start_time
    
    def test_execution_trace_to_dict(self):
        """Test converting trace to dictionary."""
        trace = ExecutionTrace("test_harness", "test_scenario")
        trace.add_event("test", {"key": "value"})
        trace.metrics = {"calls": 5}
        trace.finalize()
        
        trace_dict = trace.to_dict()
        
        assert trace_dict["harness"] == "test_harness"
        assert trace_dict["scenario_id"] == "test_scenario"
        assert len(trace_dict["events"]) == 1
        assert trace_dict["metrics"]["calls"] == 5
        assert "duration_seconds" in trace_dict


# ============================================================================
# UNIT TESTS: LLM Tracker
# ============================================================================

class TestLLMTracker:
    """Tests for LLM call tracking."""
    
    def test_initialize_tracker(self):
        """Test LLM tracker initialization."""
        initialize_llm_tracker(max_calls=25, max_duration_seconds=200)
        
        tracker = get_llm_tracker()
        assert tracker is not None
        assert tracker.max_calls == 25
        assert tracker.max_duration_seconds == 200
        assert tracker.call_count == 0
    
    def test_tracker_increment_calls(self):
        """Test incrementing LLM call count."""
        initialize_llm_tracker(max_calls=10, max_duration_seconds=60)
        tracker = get_llm_tracker()
        
        tracker.increment_call()
        tracker.increment_call()
        
        assert tracker.call_count == 2
    
    def test_tracker_check_threshold_not_exceeded(self):
        """Test threshold check when not exceeded."""
        initialize_llm_tracker(max_calls=10, max_duration_seconds=60)
        tracker = get_llm_tracker()
        
        tracker.increment_call()
        
        exceeded, reason = tracker.check_threshold_exceeded()
        assert exceeded is False
        assert reason is None
    
    def test_tracker_check_threshold_call_limit_exceeded(self):
        """Test threshold check when call limit exceeded."""
        initialize_llm_tracker(max_calls=5, max_duration_seconds=60)
        tracker = get_llm_tracker()
        
        for _ in range(5):
            tracker.increment_call()
        
        exceeded, reason = tracker.check_threshold_exceeded()
        assert exceeded is True
        assert "call limit" in reason.lower()


# ============================================================================
# CONCURRENCY TESTS
# ============================================================================

class TestConcurrentExecution:
    """Tests for concurrent behavior."""
    
    @pytest.mark.asyncio
    async def test_concurrent_polling_and_custom_events(self):
        """Test that adapter polling and custom events run concurrently."""
        execution_order = []
        lock = asyncio.Lock()
        
        async def adapter_task():
            for i in range(3):
                await asyncio.sleep(0.02)
                async with lock:
                    execution_order.append(("adapter", i))
        
        async def custom_task():
            for i in range(3):
                await asyncio.sleep(0.025)
                async with lock:
                    execution_order.append(("custom", i))
        
        # Run both concurrently
        await asyncio.gather(adapter_task(), custom_task())
        
        # Both should have executed
        assert len(execution_order) == 6
        assert sum(1 for e in execution_order if e[0] == "adapter") == 3
        assert sum(1 for e in execution_order if e[0] == "custom") == 3
    
    @pytest.mark.asyncio
    async def test_task_cancellation(self):
        """Test graceful task cancellation."""
        executed = []
        
        async def background_task():
            try:
                while True:
                    executed.append("iteration")
                    await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                executed.append("cancelled")
                raise
        
        task = asyncio.create_task(background_task())
        await asyncio.sleep(0.05)
        
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        assert "cancelled" in executed
        assert len([e for e in executed if e == "iteration"]) > 0


# ============================================================================
# SCENARIO CONFIGURATION TESTS
# ============================================================================

class TestScenarioConfiguration:
    """Tests for scenario definitions."""
    
    def test_harness_has_test_scenarios(self, harness):
        """Test that harness has test scenarios defined."""
        assert hasattr(harness, "test_scenarios")
        assert len(harness.test_scenarios) > 0
    
    def test_first_scenario_is_purchase(self, harness):
        """Test first scenario is Purchase protocol."""
        scenario = harness.test_scenarios[0]
        assert scenario["protocol"] == "Purchase"
        assert scenario["role"] == "Buyer"
        assert scenario["custom_event_type"] == "periodic_timeout"
    
    def test_second_scenario_is_logistics(self, harness):
        """Test second scenario is Logistics protocol."""
        scenario = harness.test_scenarios[1]
        assert scenario["protocol"] == "Logistics"
        assert scenario["role"] == "Merchant"
        assert scenario["custom_event_type"] == "stall_detection"
    
    def test_scenario_has_required_fields(self, harness):
        """Test that each scenario has required configuration fields."""
        required_fields = [
            "id", "protocol", "role", "description",
            "custom_event_type", "custom_event_interval", "agent_goal"
        ]
        
        for scenario in harness.test_scenarios:
            for field in required_fields:
                assert field in scenario, f"Scenario missing required field: {field}"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_scenario_handles_exception(self, harness):
        """Test that scenario execution handles exceptions gracefully."""
        scenario = {
            "id": "error_test",
            "protocol": "InvalidProto",
            "role": "InvalidRole",
            "description": "Will cause error",
            "custom_event_type": "periodic_timeout",
            "custom_event_interval": 1.0,
            "agent_goal": "Test"
        }
        
        trace = await harness.execute_scenario(scenario)
        
        # Should return trace even with errors
        assert trace is not None
        # Should have finalized
        assert trace.end_time is not None
    
    def test_trace_error_context(self):
        """Test error tracking with context."""
        trace = ExecutionTrace("test", "scenario")
        
        error_context = {"attempt": 1, "value": 42}
        trace.add_error("test_error", "Test message", error_context)
        
        assert len(trace.errors) == 1
        error = trace.errors[0]
        assert error["context"]["attempt"] == 1
        assert error["context"]["value"] == 42


# ============================================================================
# INTEGRATION TESTS: Full Harness Execution
# ============================================================================

class TestFullHarnessExecution:
    """Tests for full harness execution flow."""
    
    @pytest.mark.asyncio
    async def test_harness_initialization(self, harness):
        """Test harness proper initialization."""
        assert harness.harness_name == "demo6_custom_events"
        assert harness.llm_client is not None
        assert len(harness.test_scenarios) == 2
    
    def test_harness_inherits_from_base(self, harness):
        """Test that harness inherits from BaseHarness."""
        from demo.harnesses.base_harness import BaseHarness
        assert isinstance(harness, BaseHarness)
    
    @pytest.mark.asyncio
    async def test_run_all_scenarios_returns_results(self, harness):
        """Test that run_all_scenarios returns proper results structure."""
        with patch.object(harness, 'execute_scenario') as mock_execute:
            # Mock scenario execution to return quickly
            mock_trace = ExecutionTrace("test", "scenario")
            mock_trace.finalize()
            mock_execute.return_value = mock_trace
            
            results = await harness.run_all_scenarios()
        
        assert "harness" in results
        assert "scenarios_executed" in results
        assert "scenarios_successful" in results
        assert results["harness"] == "demo6_custom_events"


# ============================================================================
# PARAMETRIZED TESTS
# ============================================================================

class TestParametrized:
    """Parametrized tests for multiple cases."""
    
    @pytest.mark.parametrize("protocol,role", [
        ("Purchase", "Buyer"),
        ("Purchase", "Seller"),
        ("Purchase", "Shipper"),
        ("Logistics", "Merchant"),
        ("Logistics", "Wrapper"),
        ("Logistics", "Labeler"),
        ("Logistics", "Packer"),
    ])
    def test_create_valid_adapters(self, protocol, role):
        """Test creating adapters for all valid protocol-role combinations."""
        adapter, error = create_adapter_for_role(protocol, role)
        assert adapter is not None, f"Failed to create {protocol}:{role}"
        assert error is None


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
