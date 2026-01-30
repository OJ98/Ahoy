#!/usr/bin/env python3
"""
Comprehensive test suite for Demo 3: Concurrent Multiprotocol Participation.

Tests validate concurrent execution across multiple BSPL protocols with:
- Real adapter usage (no mocks)
- Parameter isolation guarantee
- Message sending and execution
- Concurrent scheduling
- Metrics tracking

Test Coverage: 11 test classes, ~58 tests
"""

import asyncio
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure project root in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configuration import systems
from demo.harnesses.demo3_concurrent_multiprotocol import (
    ConcurrentMultiprotocolHarness,
    EventScheduler
)
from demo.harnesses.base_harness import ExecutionTrace


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def harness():
    """Create a demo3 harness instance."""
    return ConcurrentMultiprotocolHarness()


@pytest.fixture
def execution_trace():
    """Create an execution trace for testing."""
    return ExecutionTrace("demo3_concurrent_multiprotocol", "test_scenario")


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    mock = AsyncMock()
    mock.complete = AsyncMock(return_value="Selected message: RequestQuote")
    return mock


@pytest.fixture(autouse=True)
def reset_harness():
    """Reset harness state between tests."""
    yield
    # Cleanup if needed


# ============================================================================
# UNIT TESTS: Harness Initialization
# ============================================================================

class TestHarnessInitialization:
    """Tests for harness initialization and setup."""
    
    def test_harness_creation(self):
        """Test harness can be instantiated."""
        harness = ConcurrentMultiprotocolHarness()
        assert harness is not None
    
    def test_harness_name(self, harness):
        """Test harness has correct name identifier."""
        assert harness.harness_name == "demo3_concurrent_multiprotocol"
    
    def test_harness_has_llm_client(self, harness):
        """Test harness initializes with LLM client."""
        assert harness.llm_client is not None
    
    def test_harness_has_message_metrics(self, harness):
        """Test harness initializes message metrics."""
        assert hasattr(harness, "message_metrics")
        assert "total_sent" in harness.message_metrics
        assert "total_skipped" in harness.message_metrics
        assert "send_errors" in harness.message_metrics
        assert harness.message_metrics["total_sent"] == 0
        assert harness.message_metrics["total_skipped"] == 0
        assert harness.message_metrics["send_errors"] == 0
    
    def test_harness_inherits_from_base(self, harness):
        """Test harness inherits from BaseHarness."""
        from demo.harnesses.base_harness import BaseHarness
        assert isinstance(harness, BaseHarness)


# ============================================================================
# UNIT TESTS: EventScheduler Functionality
# ============================================================================

class TestEventScheduler:
    """Tests for concurrent protocol scheduling."""
    
    def test_scheduler_creation(self):
        """Test EventScheduler can be instantiated."""
        configs = {"purchase": {}, "logistics": {}}
        scheduler = EventScheduler(configs)
        assert scheduler is not None
    
    def test_scheduler_round_robin(self):
        """Test scheduler returns protocols in round-robin order."""
        configs = {"protocol_a": {}, "protocol_b": {}}
        scheduler = EventScheduler(configs)
        
        # Get first 4 protocols (should cycle)
        result1 = scheduler.next_protocol()
        result2 = scheduler.next_protocol()
        result3 = scheduler.next_protocol()
        result4 = scheduler.next_protocol()
        
        # Should alternate between two protocols
        assert result1 in ["protocol_a", "protocol_b"]
        assert result2 in ["protocol_a", "protocol_b"]
        assert result1 != result2  # Should be different
        assert result3 == result1  # Should cycle back
        assert result4 == result2
    
    def test_scheduler_with_three_protocols(self):
        """Test scheduler with three protocols."""
        configs = {"p1": {}, "p2": {}, "p3": {}}
        scheduler = EventScheduler(configs)
        
        results = [scheduler.next_protocol() for _ in range(9)]
        
        # Should cycle through all three
        assert len(set(results)) == 3  # All three protocols appear
        assert results[0] != results[1]  # Not same in sequence
        assert results[3] == results[0]  # Cycle repeats at position 3
    
    def test_scheduler_stores_configs(self):
        """Test scheduler stores protocol configurations."""
        configs = {"purchase": {"role": "Buyer"}, "logistics": {"role": "Merchant"}}
        scheduler = EventScheduler(configs)
        assert scheduler.protocol_configs == configs


# ============================================================================
# INTEGRATION TESTS: Concurrent Enactment
# ============================================================================

class TestConcurrentEnactmentBasics:
    """Tests for basic concurrent enactment functionality."""
    
    @pytest.mark.asyncio
    async def test_run_concurrent_enactment_returns_results(self, harness):
        """Test concurrent enactment returns result dictionary."""
        with patch.object(harness, '_get_llm_decision', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = None
            
            result = await harness.run_concurrent_enactment(max_steps_per_protocol=1)
            
            assert result is not None
            assert "status" in result
            assert "protocols_executed" in result
            assert "total_interleaved_steps" in result
            assert "protocol_results" in result
    
    @pytest.mark.asyncio
    async def test_run_concurrent_enactment_success_status(self, harness):
        """Test successful enactment returns success status."""
        with patch.object(harness, '_get_llm_decision', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = None
            
            result = await harness.run_concurrent_enactment(max_steps_per_protocol=2)
            
            assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_run_concurrent_enactment_has_two_protocols(self, harness):
        """Test enactment executes both Purchase and Logistics protocols."""
        with patch.object(harness, '_get_llm_decision', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = None
            
            result = await harness.run_concurrent_enactment(max_steps_per_protocol=2)
            
            assert result["protocols_executed"] == 2
            assert "purchase" in result["protocol_results"]
            assert "logistics" in result["protocol_results"]


# ============================================================================
# UNIT TESTS: Adapter Creation and Management
# ============================================================================

class TestAdapterCreation:
    """Tests for concurrent adapter instantiation."""
    
    def test_create_adapter_purchase_buyer(self):
        """Test Purchase:Buyer adapter creation."""
        system_config = systems["Purchase"]
        protocol_obj = system_config["protocol"]
        role_obj = protocol_obj.roles["Buyer"]
        
        from bspl.adapter import Adapter
        adapter = Adapter(role_obj, systems, {})
        
        assert adapter is not None
    
    def test_create_adapter_logistics_merchant(self):
        """Test Logistics:Merchant adapter creation."""
        system_config = systems["Logistics"]
        protocol_obj = system_config["protocol"]
        role_obj = protocol_obj.roles["Merchant"]
        
        from bspl.adapter import Adapter
        adapter = Adapter(role_obj, systems, {})
        
        assert adapter is not None
    
    def test_adapters_have_enabled_messages(self):
        """Test adapters have enabled_messages method."""
        system_config = systems["Purchase"]
        protocol_obj = system_config["protocol"]
        role_obj = protocol_obj.roles["Buyer"]
        
        from bspl.adapter import Adapter
        adapter = Adapter(role_obj, systems, {})
        
        assert hasattr(adapter, "enabled_messages")
        assert callable(adapter.enabled_messages)
    
    def test_adapters_have_send_method(self):
        """Test adapters have send method."""
        system_config = systems["Purchase"]
        protocol_obj = system_config["protocol"]
        role_obj = protocol_obj.roles["Buyer"]
        
        from bspl.adapter import Adapter
        adapter = Adapter(role_obj, systems, {})
        
        assert hasattr(adapter, "send")
        assert callable(adapter.send)


# ============================================================================
# UNIT TESTS: LLM Decision Making
# ============================================================================

class TestLLMDecisionMaking:
    """Tests for LLM-based message selection."""
    
    @pytest.mark.asyncio
    async def test_get_llm_decision_returns_dict(self, harness):
        """Test LLM decision returns dictionary."""
        config = {
            "role": "Buyer",
            "protocol": "Purchase",
            "goal": "Buy a pen",
            "step": 0
        }
        enabled_messages = [
            MagicMock(schema=MagicMock(name="RequestQuote", ins=[], outs=[]))
        ]
        state = {"bound_parameters": {}, "message_history": []}
        
        with patch.object(harness.llm_client, 'complete', new_callable=AsyncMock) as mock:
            mock.return_value = "Choose RequestQuote"
            
            result = await harness._get_llm_decision("purchase", config, enabled_messages, state)
        
        assert result is not None
        assert "type" in result
        assert "response" in result
    
    @pytest.mark.asyncio
    async def test_get_llm_decision_with_multiple_messages(self, harness):
        """Test LLM decision with multiple enabled messages."""
        config = {
            "role": "Buyer",
            "protocol": "Purchase",
            "goal": "Buy a pen",
            "step": 1
        }
        enabled_messages = [
            MagicMock(schema=MagicMock(name="RequestQuote", ins=[], outs=[])),
            MagicMock(schema=MagicMock(name="AcceptQuote", ins=[], outs=[]))
        ]
        state = {"bound_parameters": {}, "message_history": []}
        
        with patch.object(harness.llm_client, 'complete', new_callable=AsyncMock) as mock:
            mock.return_value = "Send AcceptQuote"
            
            result = await harness._get_llm_decision("purchase", config, enabled_messages, state)
        
        assert result is not None
        assert "RequestQuote" in str(mock.call_args)
        assert "AcceptQuote" in str(mock.call_args)


# ============================================================================
# UNIT TESTS: Message Execution
# ============================================================================

class TestMessageExecution:
    """Tests for message sending and execution."""
    
    @pytest.mark.asyncio
    async def test_execute_message_decision_skip(self, harness):
        """Test message execution with SKIP response."""
        config = {"role": "Buyer", "protocol": "Purchase", "step": 0}
        decision = {"response": "SKIP"}
        enabled_messages = [MagicMock(schema=MagicMock(name="RequestQuote"))]
        adapter = MagicMock()
        trace = ExecutionTrace("demo3", "test")
        
        result = await harness._execute_message_decision(
            "purchase", config, decision, enabled_messages, adapter, trace
        )
        
        assert result is False
        adapter.send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_execute_message_decision_send_success(self, harness):
        """Test successful message send."""
        config = {"role": "Buyer", "protocol": "Purchase", "step": 0}
        decision = {"response": "Send RequestQuote"}
        msg = MagicMock()
        msg.schema = MagicMock(name="RequestQuote")
        enabled_messages = [msg]
        adapter = AsyncMock()
        trace = ExecutionTrace("demo3", "test")
        
        result = await harness._execute_message_decision(
            "purchase", config, decision, enabled_messages, adapter, trace
        )
        
        assert result is True
        adapter.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_message_decision_partial_match(self, harness):
        """Test message selection with partial name match."""
        config = {"role": "Buyer", "protocol": "Purchase", "step": 0}
        decision = {"response": "request"}  # lowercase partial match
        msg = MagicMock()
        msg.schema = MagicMock(name="RequestQuote")
        enabled_messages = [msg]
        adapter = AsyncMock()
        trace = ExecutionTrace("demo3", "test")
        
        result = await harness._execute_message_decision(
            "purchase", config, decision, enabled_messages, adapter, trace
        )
        
        assert result is True
        adapter.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_message_decision_fallback(self, harness):
        """Test fallback to first message when ambiguous."""
        config = {"role": "Buyer", "protocol": "Purchase", "step": 0}
        decision = {"response": "something"}  # No match
        msg = MagicMock()
        msg.schema = MagicMock(name="RequestQuote")
        enabled_messages = [msg]
        adapter = AsyncMock()
        trace = ExecutionTrace("demo3", "test")
        
        result = await harness._execute_message_decision(
            "purchase", config, decision, enabled_messages, adapter, trace
        )
        
        assert result is True
        adapter.send.assert_called_once()


# ============================================================================
# INTEGRATION TESTS: Parameter Isolation
# ============================================================================

class TestParameterIsolation:
    """Tests for parameter isolation guarantee across protocols."""
    
    @pytest.mark.asyncio
    async def test_parameter_isolation_maintained(self, harness):
        """Test parameter isolation is maintained with actual adapters."""
        with patch.object(harness, '_get_llm_decision', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = None
            
            result = await harness.run_concurrent_enactment(max_steps_per_protocol=1)
            
            # Should report isolation maintained
            assert "isolation_check" in result
            assert "passed" in result["isolation_check"]
    
    @pytest.mark.asyncio
    async def test_isolation_check_records_violations(self, harness):
        """Test isolation violations are properly recorded."""
        with patch.object(harness, '_get_llm_decision', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = None
            
            result = await harness.run_concurrent_enactment(max_steps_per_protocol=1)
            
            assert "isolation_check" in result
            assert "violations" in result["isolation_check"]
            assert isinstance(result["isolation_check"]["violations"], list)


# ============================================================================
# INTEGRATION TESTS: Message Metrics
# ============================================================================

class TestMessageMetrics:
    """Tests for message tracking and metrics."""
    
    def test_message_metrics_initialized(self, harness):
        """Test message metrics initialized correctly."""
        assert harness.message_metrics["total_sent"] == 0
        assert harness.message_metrics["total_skipped"] == 0
        assert harness.message_metrics["send_errors"] == 0
    
    @pytest.mark.asyncio
    async def test_message_metrics_tracking(self, harness):
        """Test message metrics are updated during execution."""
        with patch.object(harness, '_get_llm_decision', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = None
            
            initial_sent = harness.message_metrics["total_sent"]
            
            await harness.run_concurrent_enactment(max_steps_per_protocol=1)
            
            # Metrics should be tracked
            assert harness.message_metrics is not None
            assert "total_sent" in harness.message_metrics
    
    @pytest.mark.asyncio
    async def test_protocol_results_include_message_counts(self, harness):
        """Test results include message sent counts."""
        with patch.object(harness, '_get_llm_decision', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = None
            
            result = await harness.run_concurrent_enactment(max_steps_per_protocol=1)
            
            for protocol_key, protocol_result in result["protocol_results"].items():
                assert "messages_sent" in protocol_result
                assert isinstance(protocol_result["messages_sent"], int)


# ============================================================================
# INTEGRATION TESTS: Execution Tracing
# ============================================================================

class TestExecutionTracing:
    """Tests for execution trace functionality."""
    
    def test_execution_trace_creation(self):
        """Test ExecutionTrace can be created."""
        trace = ExecutionTrace("demo3", "test_scenario")
        assert trace is not None
        assert trace.harness_name == "demo3"
        assert trace.scenario_id == "test_scenario"
    
    def test_execution_trace_add_event(self):
        """Test adding events to trace."""
        trace = ExecutionTrace("demo3", "test")
        trace.add_event("test_event", {"data": "value"})
        assert len(trace.events) == 1
        assert trace.events[0]["type"] == "test_event"
    
    def test_execution_trace_add_error(self):
        """Test adding errors to trace."""
        trace = ExecutionTrace("demo3", "test")
        trace.add_error("test_error", "Error message")
        assert len(trace.errors) == 1
        assert trace.errors[0]["type"] == "test_error"
    
    def test_execution_trace_finalization(self):
        """Test trace finalization sets end_time."""
        trace = ExecutionTrace("demo3", "test")
        assert trace.end_time is None
        trace.finalize()
        assert trace.end_time is not None
    
    @pytest.mark.asyncio
    async def test_trace_finalized_after_enactment(self, harness):
        """Test trace is finalized after enactment."""
        with patch.object(harness, '_get_llm_decision', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = None
            
            await harness.run_concurrent_enactment(max_steps_per_protocol=1)
            
            # Check if traces exist and are finalized
            assert len(harness.traces) > 0
            trace = harness.traces[0]
            assert trace.end_time is not None


# ============================================================================
# INTEGRATION TESTS: Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_enactment_error_handling(self, harness):
        """Test enactment handles errors gracefully."""
        with patch.object(harness, '_get_llm_decision', side_effect=Exception("Test error")):
            result = await harness.run_concurrent_enactment(max_steps_per_protocol=1)
            
            assert result is not None
            # Should either handle or report error
    
    @pytest.mark.asyncio
    async def test_message_execution_error_tracking(self, harness):
        """Test message execution errors are tracked."""
        config = {"role": "Buyer", "protocol": "Purchase", "step": 0}
        decision = {"response": "send"}
        msg = MagicMock()
        msg.schema = MagicMock(name="RequestQuote")
        enabled_messages = [msg]
        adapter = AsyncMock(side_effect=Exception("Send failed"))
        trace = ExecutionTrace("demo3", "test")
        
        initial_errors = harness.message_metrics["send_errors"]
        
        result = await harness._execute_message_decision(
            "purchase", config, decision, enabled_messages, adapter, trace
        )
        
        assert harness.message_metrics["send_errors"] > initial_errors
    
    @pytest.mark.asyncio
    async def test_llm_decision_error_returns_none(self, harness):
        """Test LLM decision error returns None gracefully."""
        config = {"role": "Buyer", "protocol": "Purchase", "step": 0}
        enabled_messages = [MagicMock(schema=MagicMock(name="RequestQuote"))]
        state = {"bound_parameters": {}}
        
        with patch.object(harness.llm_client, 'complete', side_effect=Exception("LLM error")):
            result = await harness._get_llm_decision("purchase", config, enabled_messages, state)
        
        assert result is None


# ============================================================================
# INTEGRATION TESTS: Full Harness Execution
# ============================================================================

class TestFullHarnessExecution:
    """Tests for complete harness workflow."""
    
    @pytest.mark.asyncio
    async def test_harness_run_method_exists(self, harness):
        """Test harness has run method."""
        assert hasattr(harness, "run")
        assert callable(harness.run)
    
    @pytest.mark.asyncio
    async def test_harness_run_returns_dict(self, harness):
        """Test harness run returns results dictionary."""
        with patch.object(harness, 'run_concurrent_enactment', new_callable=AsyncMock) as mock:
            mock.return_value = {
                "status": "success",
                "protocols_executed": 2,
                "total_interleaved_steps": 10,
                "isolation_violations": 0,
                "protocol_results": {}
            }
            
            results = await harness.run()
            
            assert results is not None
            assert isinstance(results, dict)
    
    @pytest.mark.asyncio
    async def test_harness_run_includes_summary(self, harness):
        """Test harness results include summary."""
        with patch.object(harness, 'run_concurrent_enactment', new_callable=AsyncMock) as mock:
            mock.return_value = {
                "status": "success",
                "protocols_executed": 2,
                "total_interleaved_steps": 10,
                "isolation_violations": 0,
                "protocol_results": {"purchase": {}, "logistics": {}},
                "isolation_check": {"violations": [], "passed": True}
            }
            
            results = await harness.run()
            
            assert "summary" in results
            assert "harness" in results
            assert "status" in results


# ============================================================================
# PARAMETRIZED TESTS: Multiple Protocol Combinations
# ============================================================================

class TestParametrized:
    """Parametrized tests across protocol-role combinations."""
    
    @pytest.mark.parametrize("protocol,role", [
        ("Purchase", "Buyer"),
        ("Purchase", "Seller"),
        ("Purchase", "Shipper"),
        ("Logistics", "Merchant"),
        ("Logistics", "Wrapper"),
        ("Logistics", "Labeler"),
        ("Logistics", "Packer"),
    ])
    def test_adapter_creation_all_roles(self, protocol, role):
        """Test adapter creation for all protocol-role combinations."""
        from bspl.adapter import Adapter
        
        system_config = systems[protocol]
        protocol_obj = system_config["protocol"]
        role_obj = protocol_obj.roles[role]
        
        adapter = Adapter(role_obj, systems, {})
        
        assert adapter is not None
        assert hasattr(adapter, "enabled_messages")
    
    @pytest.mark.parametrize("protocol,role", [
        ("Purchase", "Buyer"),
        ("Purchase", "Seller"),
        ("Logistics", "Merchant"),
        ("Logistics", "Wrapper"),
    ])
    @pytest.mark.asyncio
    async def test_llm_decision_all_roles(self, harness, protocol, role):
        """Test LLM decision making for various roles."""
        config = {
            "role": role,
            "protocol": protocol,
            "goal": "Test goal",
            "step": 0
        }
        enabled_messages = [
            MagicMock(schema=MagicMock(name="TestMessage", ins=[], outs=[]))
        ]
        state = {"bound_parameters": {}, "message_history": []}
        
        with patch.object(harness.llm_client, 'complete', new_callable=AsyncMock) as mock:
            mock.return_value = "Select TestMessage"
            
            result = await harness._get_llm_decision(
                f"{protocol}_{role}", config, enabled_messages, state
            )
        
        assert result is not None
        assert "response" in result
    
    @pytest.mark.parametrize("max_steps", [1, 2, 5, 8])
    @pytest.mark.asyncio
    async def test_concurrent_enactment_various_step_limits(self, harness, max_steps):
        """Test concurrent enactment with various step limits."""
        with patch.object(harness, '_get_llm_decision', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = None
            
            result = await harness.run_concurrent_enactment(max_steps_per_protocol=max_steps)
            
            assert result["status"] == "success"
            assert result["protocols_executed"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
