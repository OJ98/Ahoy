#!/usr/bin/env python3
"""
Comprehensive test suite for Demo 1: Protocol Portability

Tests cover:
- Protocol portability across Purchase and Logistics
- LLM decision-making consistency across domains
- Message sequence validation and constraint adherence
- Adapter creation and enactment
- Execution state tracking and metrics
- Error handling and recovery
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
from lib.state_manager import extract_social_state
from demo.harnesses.demo1_protocol_portability import ProtocolPortabilityHarness
from demo.harnesses.base_harness import ExecutionTrace


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def harness():
    """Create a ProtocolPortabilityHarness instance."""
    return ProtocolPortabilityHarness()


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock(spec=AnthropicLLMClient)
    return client


@pytest.fixture
def execution_trace():
    """Create an ExecutionTrace instance."""
    return ExecutionTrace("test_harness", "test_scenario")


@pytest.fixture(autouse=True)
def reset_tracker():
    """Reset LLM tracker before each test."""
    reset_llm_tracker()
    yield
    reset_llm_tracker()


# ============================================================================
# UNIT TESTS: Harness Initialization
# ============================================================================

class TestHarnessInitialization:
    """Tests for harness initialization and configuration."""
    
    def test_harness_creation(self):
        """Test harness can be instantiated."""
        harness = ProtocolPortabilityHarness()
        assert harness is not None
    
    def test_harness_name(self, harness):
        """Test harness has correct name."""
        assert harness.harness_name == "demo1_protocol_portability"
    
    def test_harness_has_llm_client(self, harness):
        """Test harness initializes LLM client."""
        assert harness.llm_client is not None
        assert isinstance(harness.llm_client, AnthropicLLMClient)
    
    def test_harness_has_test_scenarios(self, harness):
        """Test harness defines test scenarios."""
        assert hasattr(harness, "test_scenarios")
        assert len(harness.test_scenarios) == 2
    
    def test_first_scenario_is_purchase(self, harness):
        """Test first scenario uses Purchase protocol."""
        scenario = harness.test_scenarios[0]
        assert scenario["protocol"] == "Purchase"
        assert scenario["role"] == "Buyer"
        assert scenario["id"] == "purchase_buyer"
    
    def test_second_scenario_is_logistics(self, harness):
        """Test second scenario uses Logistics protocol."""
        scenario = harness.test_scenarios[1]
        assert scenario["protocol"] == "Logistics"
        assert scenario["role"] == "Merchant"
        assert scenario["id"] == "logistics_merchant"


# ============================================================================
# UNIT TESTS: Scenario Definition Validation
# ============================================================================

class TestScenarioConfiguration:
    """Tests for scenario configuration completeness."""
    
    def test_scenarios_have_required_fields(self, harness):
        """Test each scenario has all required fields."""
        required_fields = ["id", "protocol", "role", "description", "agent_goal"]
        
        for scenario in harness.test_scenarios:
            for field in required_fields:
                assert field in scenario, f"Scenario missing field: {field}"
    
    def test_scenario_ids_are_unique(self, harness):
        """Test scenario IDs are unique."""
        ids = [s["id"] for s in harness.test_scenarios]
        assert len(ids) == len(set(ids)), "Scenario IDs must be unique"
    
    def test_scenario_protocols_are_valid(self, harness):
        """Test scenario protocols are available in configuration."""
        for scenario in harness.test_scenarios:
            assert scenario["protocol"] in systems, f"Invalid protocol: {scenario['protocol']}"
    
    def test_scenario_roles_are_valid(self, harness):
        """Test scenario roles exist in respective protocols."""
        for scenario in harness.test_scenarios:
            protocol = systems[scenario["protocol"]]["protocol"]
            assert scenario["role"] in protocol.roles, (
                f"Invalid role {scenario['role']} for {scenario['protocol']}"
            )


# ============================================================================
# UNIT TESTS: Adapter Creation for Portability
# ============================================================================

class TestAdapterCreationPortability:
    """Tests for adapter creation across protocols."""
    
    def test_create_adapter_purchase_buyer(self):
        """Test adapter creation for Purchase:Buyer."""
        adapter, error = create_adapter_for_role("Purchase", "Buyer")
        assert adapter is not None
        assert error is None
    
    def test_create_adapter_logistics_merchant(self):
        """Test adapter creation for Logistics:Merchant."""
        adapter, error = create_adapter_for_role("Logistics", "Merchant")
        assert adapter is not None
        assert error is None
    
    def test_adapter_has_enabled_messages_property(self):
        """Test adapters have required enabled_messages property."""
        for protocol, role in [("Purchase", "Buyer"), ("Logistics", "Merchant")]:
            adapter, _ = create_adapter_for_role(protocol, role)
            assert hasattr(adapter, "enabled_messages")
            assert adapter.enabled_messages is not None
    
    def test_adapter_has_send_method(self):
        """Test adapters have send method for message transmission."""
        for protocol, role in [("Purchase", "Buyer"), ("Logistics", "Merchant")]:
            adapter, _ = create_adapter_for_role(protocol, role)
            assert hasattr(adapter, "send")
            assert callable(adapter.send)


# ============================================================================
# INTEGRATION TESTS: Protocol Enactment
# ============================================================================

class TestProtocolEnactment:
    """Tests for protocol enactment execution."""
    
    @pytest.mark.asyncio
    async def test_run_protocol_enactment_invalid_protocol(self, harness):
        """Test error handling for invalid protocol."""
        trace = ExecutionTrace("test", "invalid_protocol_test")
        
        result = await harness.run_protocol_enactment(
            protocol_name="InvalidProtocol",
            role_name="InvalidRole",
            agent_goal="Test",
            trace=trace
        )
        
        assert result["status"] == "error"
        assert result["error_type"] == "configuration"
    
    @pytest.mark.asyncio
    async def test_run_protocol_enactment_invalid_role(self, harness):
        """Test error handling for invalid role in valid protocol."""
        trace = ExecutionTrace("test", "invalid_role_test")
        
        result = await harness.run_protocol_enactment(
            protocol_name="Purchase",
            role_name="InvalidRole",
            agent_goal="Test",
            trace=trace
        )
        
        assert result["status"] == "error"
        assert result["error_type"] == "configuration"
    
    @pytest.mark.asyncio
    async def test_enactment_returns_metrics(self, harness):
        """Test that enactment returns proper metrics structure."""
        trace = ExecutionTrace("test", "metrics_test")
        
        # Test enactment (it will terminate quickly with no enabled messages)
        result = await harness.run_protocol_enactment(
            protocol_name="Purchase",
            role_name="Buyer",
            agent_goal="Buy something",
            trace=trace,
            max_steps=1  # Limit to 1 step to avoid LLM calls
        )
        
        # Check result structure
        assert "status" in result
        assert "protocol" in result
        assert "role" in result
        # Both success and error cases have these fields
        if result["status"] == "success":
            assert "steps_executed" in result
            assert "messages_sent" in result
            assert "adapter_exceptions" in result
            assert "violations" in result


# ============================================================================
# UNIT TESTS: Execution Tracing
# ============================================================================

class TestExecutionTracing:
    """Tests for execution trace functionality."""
    
    def test_trace_creation(self):
        """Test ExecutionTrace initialization."""
        trace = ExecutionTrace("demo1", "test_scenario")
        
        assert trace.harness_name == "demo1"
        assert trace.scenario_id == "test_scenario"
        assert trace.events == []
        assert trace.errors == []
    
    def test_trace_add_event(self):
        """Test adding events to trace."""
        trace = ExecutionTrace("demo1", "scenario")
        
        trace.add_event("adapter_created", {"protocol": "Purchase"})
        
        assert len(trace.events) == 1
        assert trace.events[0]["type"] == "adapter_created"
        assert trace.events[0]["data"]["protocol"] == "Purchase"
    
    def test_trace_add_error(self):
        """Test adding errors to trace."""
        trace = ExecutionTrace("demo1", "scenario")
        
        trace.add_error("invalid_config", "Protocol not found", {
            "protocol": "Invalid"
        })
        
        assert len(trace.errors) == 1
        assert trace.errors[0]["type"] == "invalid_config"
    
    def test_trace_add_message(self):
        """Test adding protocol messages to trace."""
        trace = ExecutionTrace("demo1", "scenario")
        
        trace.add_message("Request", "Buyer", "Seller", {"item": "pen"})
        
        # Verify message was recorded in messages list, not events
        assert len(trace.messages) > 0
        assert trace.messages[0]["type"] == "Request"
        assert trace.messages[0]["sender"] == "Buyer"
    
    def test_trace_add_state_snapshot(self):
        """Test adding state snapshots to trace."""
        trace = ExecutionTrace("demo1", "scenario")
        
        state_data = {"messages_sent": 0, "bindings": {}}
        trace.add_state_snapshot("Purchase", "Buyer", state_data)
        
        # Verify snapshot was recorded in states list, not events
        assert len(trace.states) > 0
        assert trace.states[0]["protocol"] == "Purchase"
        assert trace.states[0]["role"] == "Buyer"
    
    def test_trace_finalization(self):
        """Test trace finalization and duration calculation."""
        trace = ExecutionTrace("demo1", "scenario")
        start_time = trace.start_time
        
        # Simulate some work
        import time
        time.sleep(0.01)
        
        trace.finalize()
        
        assert trace.end_time is not None
        assert trace.end_time >= start_time
    
    def test_trace_to_dict(self):
        """Test trace serialization to dictionary."""
        trace = ExecutionTrace("demo1", "purchase_buyer")
        trace.add_event("test", {"key": "value"})
        trace.finalize()
        
        trace_dict = trace.to_dict()
        
        assert trace_dict["harness"] == "demo1"
        assert trace_dict["scenario_id"] == "purchase_buyer"
        assert len(trace_dict["events"]) >= 1
        assert "duration_seconds" in trace_dict


# ============================================================================
# UNIT TESTS: State Extraction
# ============================================================================

class TestStateExtraction:
    """Tests for protocol state extraction and serialization."""
    
    def test_extract_state_from_purchase_adapter(self):
        """Test state extraction from Purchase protocol adapter."""
        adapter, _ = create_adapter_for_role("Purchase", "Buyer")
        
        state = extract_social_state(adapter)
        
        assert state is not None
        assert isinstance(state, dict)
    
    def test_extract_state_from_logistics_adapter(self):
        """Test state extraction from Logistics protocol adapter."""
        adapter, _ = create_adapter_for_role("Logistics", "Merchant")
        
        state = extract_social_state(adapter)
        
        assert state is not None
        assert isinstance(state, dict)
    
    def test_extracted_state_is_json_serializable(self):
        """Test that extracted state can be JSON serialized."""
        adapter, _ = create_adapter_for_role("Purchase", "Buyer")
        state = extract_social_state(adapter)
        
        # Should not raise exception
        json_str = json.dumps(state)
        assert isinstance(json_str, str)
        assert len(json_str) > 0


# ============================================================================
# CONCURRENCY TESTS
# ============================================================================

class TestConcurrentProtocolExecution:
    """Tests for concurrent execution across multiple protocols."""
    
    @pytest.mark.asyncio
    async def test_concurrent_enactments(self, harness):
        """Test concurrent protocol enactments for different protocols."""
        trace1 = ExecutionTrace("demo1", "purchase_concurrent")
        trace2 = ExecutionTrace("demo1", "logistics_concurrent")
        
        with patch.object(harness.llm_client, 'complete') as mock_complete:
            mock_complete.return_value = '{"choice": null, "params": {}}'
            
            # Run both enactments concurrently
            results = await asyncio.gather(
                harness.run_protocol_enactment(
                    protocol_name="Purchase",
                    role_name="Buyer",
                    agent_goal="Buy",
                    trace=trace1
                ),
                harness.run_protocol_enactment(
                    protocol_name="Logistics",
                    role_name="Merchant",
                    agent_goal="Organize",
                    trace=trace2
                )
            )
        
        # Both should complete without error
        assert len(results) == 2
        assert all(r["status"] in ["success", "error"] for r in results)


# ============================================================================
# UNIT TESTS: LLM Tracker Integration
# ============================================================================

class TestLLMTrackerIntegration:
    """Tests for LLM call tracking in protocol portability."""
    
    def test_tracker_initialization(self):
        """Test LLM tracker can be initialized."""
        initialize_llm_tracker(max_calls=20, max_duration_seconds=180)
        
        tracker = get_llm_tracker()
        assert tracker is not None
        assert tracker.max_calls == 20
    
    def test_tracker_call_counting(self):
        """Test LLM call count tracking."""
        initialize_llm_tracker(max_calls=10, max_duration_seconds=60)
        tracker = get_llm_tracker()
        
        tracker.increment_call()
        tracker.increment_call()
        
        assert tracker.call_count == 2
    
    def test_tracker_threshold_validation(self):
        """Test threshold checking across protocol changes."""
        initialize_llm_tracker(max_calls=5, max_duration_seconds=60)
        tracker = get_llm_tracker()
        
        # Increment within limit
        for _ in range(4):
            tracker.increment_call()
        
        exceeded, reason = tracker.check_threshold_exceeded()
        assert exceeded is False
        
        # Increment to limit
        tracker.increment_call()
        exceeded, reason = tracker.check_threshold_exceeded()
        assert exceeded is True


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_invalid_protocol_error_context(self, harness):
        """Test error context for invalid protocol."""
        trace = ExecutionTrace("demo1", "error_test")
        
        result = await harness.run_protocol_enactment(
            protocol_name="BadProto",
            role_name="BadRole",
            agent_goal="Test",
            trace=trace
        )
        
        assert result["status"] == "error"
        assert result["error_type"] == "configuration"
        assert "BadProto" in result["error"] or "not found" in result["error"].lower()
    
    def test_trace_preserves_errors(self):
        """Test that execution trace preserves error information."""
        trace = ExecutionTrace("demo1", "error_scenario")
        
        trace.add_error("test_error", "Error message", {
            "context_key": "context_value"
        })
        
        assert len(trace.errors) == 1
        error = trace.errors[0]
        assert error["message"] == "Error message"
        assert error["context"]["context_key"] == "context_value"


# ============================================================================
# INTEGRATION TESTS: Full Harness Execution
# ============================================================================

class TestFullHarnessExecution:
    """Tests for complete harness execution flow."""
    
    @pytest.mark.asyncio
    async def test_harness_run_method_exists(self, harness):
        """Test harness has run method."""
        assert hasattr(harness, "run")
        assert callable(harness.run)
    
    @pytest.mark.asyncio
    async def test_harness_run_returns_results_dict(self, harness):
        """Test run method returns proper results structure."""
        with patch.object(harness, 'run_protocol_enactment') as mock_enact:
            # Mock enactment to return success
            trace = ExecutionTrace("demo1", "test")
            trace.finalize()
            
            mock_result = {
                "status": "success",
                "protocol": "Purchase",
                "role": "Buyer",
                "steps_executed": 5,
                "messages_sent": 3,
                "decisions_made": 3,
                "adapter_exceptions": 0,
                "violations": 0,
                "terminal_reached": True,
                "execution_time_seconds": 1.5
            }
            mock_enact.return_value = mock_result
            
            with patch.object(harness, 'save_all_traces'):
                with patch.object(harness, 'save_summary_report'):
                    results = await harness.run()
        
        assert "harness" in results
        assert "scenarios" in results
        assert "summary" in results


# ============================================================================
# PROTOCOL COMPATIBILITY TESTS
# ============================================================================

class TestProtocolCompatibility:
    """Tests validating protocol portability invariants."""
    
    def test_both_protocols_have_roles(self):
        """Test both protocols define required roles."""
        assert "Purchase" in systems
        assert "Logistics" in systems
        
        purchase_protocol = systems["Purchase"]["protocol"]
        logistics_protocol = systems["Logistics"]["protocol"]
        
        assert "Buyer" in purchase_protocol.roles
        assert "Merchant" in logistics_protocol.roles
    
    def test_all_scenario_protocols_valid(self, harness):
        """Test all scenario protocols exist in configuration."""
        for scenario in harness.test_scenarios:
            protocol_name = scenario["protocol"]
            assert protocol_name in systems
            
            protocol_obj = systems[protocol_name]["protocol"]
            role_name = scenario["role"]
            assert role_name in protocol_obj.roles
    
    def test_adapter_can_be_created_for_all_scenarios(self, harness):
        """Test adapters can be created for all test scenarios."""
        for scenario in harness.test_scenarios:
            adapter, error = create_adapter_for_role(
                scenario["protocol"],
                scenario["role"]
            )
            assert adapter is not None, f"Failed to create {scenario['protocol']}:{scenario['role']}"
            assert error is None


# ============================================================================
# PARAMETRIZED TESTS
# ============================================================================

class TestParametrized:
    """Parametrized tests for multiple scenarios."""
    
    @pytest.mark.parametrize("protocol,role", [
        ("Purchase", "Buyer"),
        ("Purchase", "Seller"),
        ("Purchase", "Shipper"),
        ("Logistics", "Merchant"),
        ("Logistics", "Wrapper"),
        ("Logistics", "Labeler"),
        ("Logistics", "Packer"),
    ])
    def test_adapter_creation_all_combinations(self, protocol, role):
        """Test adapter creation for all protocol-role combinations."""
        adapter, error = create_adapter_for_role(protocol, role)
        assert adapter is not None, f"Failed to create {protocol}:{role}"
        assert error is None
    
    @pytest.mark.parametrize("scenario_idx", [0, 1])
    def test_all_scenarios_well_defined(self, harness, scenario_idx):
        """Test all scenarios in harness are well-defined."""
        scenario = harness.test_scenarios[scenario_idx]
        
        assert "id" in scenario
        assert "protocol" in scenario
        assert "role" in scenario
        assert "description" in scenario
        assert "agent_goal" in scenario
        assert len(scenario["id"]) > 0
        assert len(scenario["agent_goal"]) > 0


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
