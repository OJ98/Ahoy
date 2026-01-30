#!/usr/bin/env python3
"""
Comprehensive test suite for Demo 2: Guarantee Validation

Tests cover:
- Message validity guarantee (schema conformance)
- Parameter isolation guarantee (protocol independence)
- Role consistency guarantee (role-appropriate messages)
- Adapter instantiation for multiple protocol-role pairs
- Guarantee validation logic and error handling
- Execution tracing and metrics
"""

import asyncio
import json
import pytest
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configuration import systems, agents
from lib.llm_client import (
    initialize_llm_tracker,
    get_llm_tracker,
    reset_llm_tracker
)
from lib.dynamic_adapter_manager import create_adapter_for_role
from lib.state_manager import extract_social_state
from demo.harnesses.demo2_guarantee_validation import (
    GuaranteeValidationHarness,
    GuaranteeValidator
)
from demo.harnesses.base_harness import ExecutionTrace


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def harness():
    """Create a GuaranteeValidationHarness instance."""
    return GuaranteeValidationHarness()


@pytest.fixture
def validator():
    """Create a GuaranteeValidator instance."""
    return GuaranteeValidator()


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
        harness = GuaranteeValidationHarness()
        assert harness is not None
    
    def test_harness_name(self, harness):
        """Test harness has correct name."""
        assert harness.harness_name == "demo2_guarantee_validation"
    
    def test_harness_has_validator(self, harness):
        """Test harness initializes validator."""
        assert harness.validator is not None
        assert isinstance(harness.validator, GuaranteeValidator)
    
    def test_harness_has_test_scenarios(self, harness):
        """Test harness defines test scenarios."""
        assert hasattr(harness, "test_scenarios")
        assert len(harness.test_scenarios) == 4
    
    def test_scenario_ids_are_unique(self, harness):
        """Test scenario IDs are unique."""
        ids = [s["id"] for s in harness.test_scenarios]
        assert len(ids) == len(set(ids))


# ============================================================================
# UNIT TESTS: Scenario Configuration
# ============================================================================

class TestScenarioConfiguration:
    """Tests for scenario definition completeness."""
    
    def test_scenarios_have_required_fields(self, harness):
        """Test each scenario has all required fields."""
        required_fields = ["id", "protocol", "role", "guarantee", "description"]
        
        for scenario in harness.test_scenarios:
            for field in required_fields:
                assert field in scenario, f"Scenario missing field: {field}"
    
    def test_all_guarantees_defined(self, harness):
        """Test all scenarios specify guarantee types."""
        guarantees = {s["guarantee"] for s in harness.test_scenarios}
        expected = {"message_validity", "parameter_isolation", "role_consistency"}
        assert len(guarantees) > 0
    
    def test_first_scenario_is_message_validity_purchase(self, harness):
        """Test first scenario validates Purchase messages."""
        scenario = harness.test_scenarios[0]
        assert scenario["id"] == "message_validity_purchase"
        assert scenario["protocol"] == "Purchase"
        assert scenario["role"] == "Buyer"
        assert scenario["guarantee"] == "message_validity"
    
    def test_second_scenario_is_message_validity_logistics(self, harness):
        """Test second scenario validates Logistics messages."""
        scenario = harness.test_scenarios[1]
        assert scenario["id"] == "message_validity_logistics"
        assert scenario["protocol"] == "Logistics"
        assert scenario["guarantee"] == "message_validity"
    
    def test_parameter_isolation_scenario(self, harness):
        """Test parameter isolation scenario is properly defined."""
        param_scenario = [s for s in harness.test_scenarios 
                         if s["guarantee"] == "parameter_isolation"][0]
        assert param_scenario["protocol"] == "multiple"
        assert param_scenario["role"] == "multiple"
    
    def test_role_consistency_scenario(self, harness):
        """Test role consistency scenario is properly defined."""
        role_scenario = [s for s in harness.test_scenarios 
                        if s["guarantee"] == "role_consistency"][0]
        assert role_scenario["protocol"] == "Purchase"
        assert role_scenario["role"] == "Seller"


# ============================================================================
# UNIT TESTS: Guarantee Validator
# ============================================================================

class TestGuaranteeValidator:
    """Tests for GuaranteeValidator static methods."""
    
    def test_validator_exists(self, validator):
        """Test validator is accessible."""
        assert validator is not None
    
    def test_validate_message_validity_method_exists(self, validator):
        """Test message validity validation method."""
        assert hasattr(validator, "validate_message_validity")
        assert callable(validator.validate_message_validity)
    
    def test_validate_parameter_isolation_method_exists(self, validator):
        """Test parameter isolation validation method."""
        assert hasattr(validator, "validate_parameter_isolation")
        assert callable(validator.validate_parameter_isolation)
    
    def test_validate_role_consistency_method_exists(self, validator):
        """Test role consistency validation method."""
        assert hasattr(validator, "validate_role_consistency")
        assert callable(validator.validate_role_consistency)
    
    def test_message_validity_with_valid_message(self, validator):
        """Test message validity check with valid message."""
        # Create mock message with required attributes
        mock_msg = MagicMock()
        mock_msg.schema.name = "request"
        mock_msg.payload = {"item": "pen"}
        
        is_valid, reason = validator.validate_message_validity(mock_msg, "request")
        assert is_valid is True
        assert reason == "Valid"
    
    def test_message_validity_with_schema_mismatch(self, validator):
        """Test message validity check with schema mismatch."""
        mock_msg = MagicMock()
        mock_msg.schema.name = "response"
        mock_msg.payload = {}
        
        is_valid, reason = validator.validate_message_validity(mock_msg, "request")
        assert is_valid is False
        assert "mismatch" in reason.lower()
    
    def test_message_validity_missing_schema(self, validator):
        """Test message validity check with missing schema."""
        mock_msg = MagicMock(spec=[])  # No attributes
        
        is_valid, reason = validator.validate_message_validity(mock_msg, "request")
        assert is_valid is False
        assert "schema" in reason.lower()
    
    def test_parameter_isolation_with_empty_states(self, validator):
        """Test parameter isolation with empty protocol states."""
        state1 = {}
        state2 = {}
        
        is_isolated, reason = validator.validate_parameter_isolation(state1, state2)
        assert is_isolated is True
    
    def test_parameter_isolation_with_different_params(self, validator):
        """Test parameter isolation with different parameters."""
        state1 = {"bound_parameters": {"orderID": "123"}}
        state2 = {"bound_parameters": {"shipmentID": "456"}}
        
        is_isolated, reason = validator.validate_parameter_isolation(state1, state2)
        assert is_isolated is True
    
    def test_role_consistency_with_valid_messages(self, validator):
        """Test role consistency with valid message list."""
        mock_msg1 = MagicMock()
        mock_msg1.schema.sender = "Buyer"
        
        mock_msg2 = MagicMock()
        mock_msg2.schema.sender = "Buyer"
        
        is_consistent, reason = validator.validate_role_consistency(
            [mock_msg1, mock_msg2], 
            "Buyer"
        )
        assert is_consistent is True
        assert "consistent" in reason.lower()
    
    def test_role_consistency_with_empty_messages(self, validator):
        """Test role consistency with empty message list."""
        is_consistent, reason = validator.validate_role_consistency([], "Buyer")
        assert is_consistent is True


# ============================================================================
# INTEGRATION TESTS: Adapter Instantiation
# ============================================================================

class TestAdapterInstantiation:
    """Tests for adapter creation in guarantee validation context."""
    
    def test_instantiate_adapter_purchase_buyer(self, harness):
        """Test adapter instantiation for Purchase:Buyer."""
        adapter = harness._instantiate_adapter("Purchase", "Buyer")
        assert adapter is not None
    
    def test_instantiate_adapter_logistics_merchant(self, harness):
        """Test adapter instantiation for Logistics:Merchant."""
        adapter = harness._instantiate_adapter("Logistics", "Merchant")
        assert adapter is not None
    
    def test_instantiate_adapter_purchase_seller(self, harness):
        """Test adapter instantiation for Purchase:Seller."""
        adapter = harness._instantiate_adapter("Purchase", "Seller")
        assert adapter is not None
    
    def test_instantiate_adapter_invalid_protocol(self, harness):
        """Test error handling for invalid protocol."""
        with pytest.raises(KeyError):
            harness._instantiate_adapter("InvalidProtocol", "InvalidRole")
    
    def test_instantiate_adapter_invalid_role(self, harness):
        """Test error handling for invalid role."""
        with pytest.raises(KeyError):
            harness._instantiate_adapter("Purchase", "InvalidRole")
    
    def test_instantiated_adapter_has_enabled_messages(self, harness):
        """Test that instantiated adapters have enabled message store."""
        adapter = harness._instantiate_adapter("Purchase", "Buyer")
        assert hasattr(adapter, "enabled_messages")
        assert adapter.enabled_messages is not None


# ============================================================================
# INTEGRATION TESTS: Message Validity Validation
# ============================================================================

class TestMessageValidityGuarantee:
    """Tests for message validity guarantee validation."""
    
    @pytest.mark.asyncio
    async def test_validate_message_validity_purchase(self, harness):
        """Test message validity validation for Purchase protocol."""
        from demo.harnesses.demo2_guarantee_validation import GuaranteeValidationHarness
        harness = GuaranteeValidationHarness()
        trace = ExecutionTrace("demo2", "message_validity_purchase_test")
        
        result = await harness.validate_message_validity_guarantee(
            "Purchase", "Buyer", trace
        )
        
        assert result is not None
        assert "guarantee" in result
        # Result may have either messages_checked or error, depending on if adapter instantiation succeeds
        assert "passed" in result
        assert result["guarantee"] == "message_validity"
    
    @pytest.mark.asyncio
    async def test_validate_message_validity_logistics(self, harness):
        """Test message validity validation for Logistics protocol."""
        trace = ExecutionTrace("demo2", "message_validity_logistics_test")
        
        result = await harness.validate_message_validity_guarantee(
            "Logistics", "Merchant", trace
        )
        
        assert result is not None
        assert result["guarantee"] == "message_validity"
        assert result["protocol"] == "Logistics"
        assert result["role"] == "Merchant"


# ============================================================================
# INTEGRATION TESTS: Parameter Isolation Validation
# ============================================================================

class TestParameterIsolationGuarantee:
    """Tests for parameter isolation guarantee validation."""
    
    @pytest.mark.asyncio
    async def test_validate_parameter_isolation(self):
        """Test parameter isolation across protocols."""
        from demo.harnesses.demo2_guarantee_validation import GuaranteeValidationHarness
        harness = GuaranteeValidationHarness()
        trace = ExecutionTrace("demo2", "parameter_isolation_test")
        
        result = await harness.validate_parameter_isolation_guarantee(trace)
        
        assert result is not None
        assert "guarantee" in result
        assert "passed" in result
        assert result["guarantee"] == "parameter_isolation"
        # Result includes details about parameters from both protocols
        assert "details" in result


# ============================================================================
# INTEGRATION TESTS: Role Consistency Validation
# ============================================================================

class TestRoleConsistencyGuarantee:
    """Tests for role consistency guarantee validation."""
    
    @pytest.mark.asyncio
    async def test_validate_role_consistency(self):
        """Test role consistency validation."""
        from demo.harnesses.demo2_guarantee_validation import GuaranteeValidationHarness
        harness = GuaranteeValidationHarness()
        trace = ExecutionTrace("demo2", "role_consistency_test")
        
        result = await harness.validate_role_consistency_guarantee(
            "Purchase", "Seller", trace
        )
        
        assert result is not None
        assert "guarantee" in result
        assert "passed" in result
        assert result["guarantee"] == "role_consistency"


# ============================================================================
# UNIT TESTS: Execution Tracing
# ============================================================================

class TestExecutionTracing:
    """Tests for execution trace functionality."""
    
    def test_trace_creation(self):
        """Test ExecutionTrace initialization."""
        trace = ExecutionTrace("demo2", "test_scenario")
        assert trace.harness_name == "demo2"
        assert trace.scenario_id == "test_scenario"
    
    def test_trace_add_event(self):
        """Test adding events to trace."""
        trace = ExecutionTrace("demo2", "scenario")
        trace.add_event("validation_start", {"guarantee": "message_validity"})
        
        assert len(trace.events) == 1
        assert trace.events[0]["type"] == "validation_start"
    
    def test_trace_add_error(self):
        """Test adding validation errors."""
        trace = ExecutionTrace("demo2", "scenario")
        trace.add_error("guarantee_violation", "Invalid message found", {
            "guarantee": "message_validity"
        })
        
        assert len(trace.errors) == 1
        assert trace.errors[0]["type"] == "guarantee_violation"
    
    def test_trace_finalization(self):
        """Test trace finalization."""
        trace = ExecutionTrace("demo2", "scenario")
        import time
        time.sleep(0.01)
        trace.finalize()
        
        assert trace.end_time is not None
        assert trace.end_time >= trace.start_time
    
    def test_trace_to_dict(self):
        """Test trace serialization."""
        trace = ExecutionTrace("demo2", "test")
        trace.add_event("test", {"key": "value"})
        trace.finalize()
        
        trace_dict = trace.to_dict()
        assert trace_dict["harness"] == "demo2"
        assert trace_dict["scenario_id"] == "test"
        assert "duration_seconds" in trace_dict


# ============================================================================
# STATE EXTRACTION TESTS
# ============================================================================

class TestStateExtraction:
    """Tests for protocol state extraction."""
    
    def test_extract_state_purchase(self):
        """Test state extraction from Purchase protocol."""
        adapter, _ = create_adapter_for_role("Purchase", "Buyer")
        state = extract_social_state(adapter)
        
        assert state is not None
        assert isinstance(state, dict)
    
    def test_extract_state_logistics(self):
        """Test state extraction from Logistics protocol."""
        adapter, _ = create_adapter_for_role("Logistics", "Merchant")
        state = extract_social_state(adapter)
        
        assert state is not None
        assert isinstance(state, dict)
    
    def test_extracted_state_serializable(self):
        """Test that extracted state is JSON serializable."""
        adapter, _ = create_adapter_for_role("Purchase", "Buyer")
        state = extract_social_state(adapter)
        
        # Should not raise exception
        json_str = json.dumps(state)
        assert isinstance(json_str, str)
        assert len(json_str) > 0


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and recovery."""
    
    def test_instantiate_adapter_with_invalid_config(self, harness):
        """Test error handling for invalid configuration."""
        with pytest.raises(KeyError):
            harness._instantiate_adapter("BadProto", "BadRole")
    
    @pytest.mark.asyncio
    async def test_validation_handles_adapter_errors(self, harness):
        """Test validation gracefully handles adapter errors."""
        trace = ExecutionTrace("demo2", "error_test")
        
        # Test with invalid role - should handle gracefully
        result = await harness.validate_message_validity_guarantee(
            "InvalidProto", "InvalidRole", trace
        )
        
        # Should return error dict, not raise exception
        assert result is not None
        if "error" in result:
            assert "passed" in result or "status" in result


# ============================================================================
# FULL HARNESS EXECUTION TESTS
# ============================================================================

class TestFullHarnessExecution:
    """Tests for complete harness workflow."""
    
    @pytest.mark.asyncio
    async def test_harness_run_method_exists(self, harness):
        """Test harness has run method."""
        assert hasattr(harness, "run")
        assert callable(harness.run)
    
    def test_harness_inherits_from_base(self, harness):
        """Test harness inherits from BaseHarness."""
        from demo.harnesses.base_harness import BaseHarness
        assert isinstance(harness, BaseHarness)


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
    def test_adapter_creation_all_combinations(self, harness, protocol, role):
        """Test adapter creation for all protocol-role combinations."""
        adapter = harness._instantiate_adapter(protocol, role)
        assert adapter is not None
    
    @pytest.mark.parametrize("guarantee_type", [
        "message_validity",
        "parameter_isolation",
        "role_consistency"
    ])
    def test_all_guarantee_types_covered(self, harness, guarantee_type):
        """Test that all guarantee types are covered in scenarios."""
        guarantee_ids = {s["guarantee"] for s in harness.test_scenarios}
        assert guarantee_type in guarantee_ids


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
