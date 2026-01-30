# Ahoy Demonstrations: Technical Guide

Complete experimental harnesses demonstrating key capabilities of the AHOY framework for LLM-driven multi-agent protocol execution.

---

## Quick Start

### Run All Demos

```bash
python -m demo.harnesses.master_harness
```

### Run Specific Demos

```bash
# Run only demos 1 and 5
python -m demo.harnesses.master_harness --only 1 5

# Run only custom events demo (6)
python -m demo.harnesses.master_harness --only 6

# Skip demos 3 and 4
python -m demo.harnesses.master_harness --skip 3 4

# Run individual demo
python -m demo.harnesses.demo6_custom_events
```

### Output Locations

Results are saved to `demo/results/` in demo-specific subfolders:

- **Per-Demo**: `demo{N}_{name}/`
  - `raw_results.json` - Complete execution results
  - `showcase_metrics.json` - Curated metrics highlighting demo objectives
  - `trace_*.json` - Detailed execution traces with rich DecisionEvent data
  - `summary.txt` - Human-readable summary

- **Aggregated**: 
  - `master_report.json` - Unified summary across all demos
  - `demo{N}_*.log` - Execution logs (DEBUG level)

---

## Architecture Overview

### Core Infrastructure: BaseHarness

All demonstrations inherit from `BaseHarness` which provides:

**ExecutionTrace** - Records comprehensive execution details:
- Event log (milestones, decisions, errors)
- Protocol messages exchanged
- Adapter state snapshots at key points
- Metrics (counts, durations, decision quality)
- JSON serialization for post-analysis

**BaseHarness** - Shared functionality:
- Dual logging: DEBUG to file, INFO to console
- Automatic trace finalization and serialization
- Result aggregation across scenarios
- Async/await patterns for non-blocking execution

### Design Patterns

1. **Comprehensive Tracing** - Every protocol decision and LLM interaction recorded
2. **Async/Await** - Non-blocking LLM calls with configurable timeouts
3. **Modular Harnesses** - Independent demos, composable via MasterHarness
4. **Scenario-Driven Testing** - Test cases defined as data structures, not code
5. **State Snapshots** - Protocol state captured at critical decision points

### Rich Decision Tracking

Each demonstration captures comprehensive decision context to enable post-execution analysis:

#### DecisionEvent Class

Records full context for each LLM decision point:

```python
class DecisionEvent:
    decision_id: str                    # Unique identifier (e.g., "d001")
    protocol: str                       # Protocol name (e.g., "Purchase")
    role: str                           # Role name (e.g., "Buyer")
    timestamp: str                      # ISO format timestamp
    state_before: Dict[str, Any]       # Protocol state before decision
    enabled_messages: List[str]         # Available message options
    llm_prompt: str                     # Exact prompt sent to LLM
    llm_response: Dict[str, Any]       # LLM response (parsed JSON)
    selected_message_type: str          # Message chosen
    confidence_score: float             # Decision confidence (0-1)
    reasoning: str                      # Human-readable reasoning
    state_after: Dict[str, Any]        # Protocol state after decision
    execution_time_ms: float            # Time taken in milliseconds
    consequences: List[Dict]            # Effects of this decision
```

#### Usage Pattern

```python
from demo.harnesses.base_harness import DecisionEvent

# During decision point
decision = DecisionEvent("d001", protocol="Purchase", role="Buyer")
decision.set_state_before(extract_social_state(adapter))
decision.set_enabled_messages([msg.type for msg in adapter.enabled_messages])
decision.set_llm_context(prompt=prompt_text, response=llm_response_dict)
decision.set_decision("rfq", confidence=0.95)
decision.set_reasoning("Buyer initiates purchase with RFQ")
decision.set_state_after(extract_social_state(adapter))
decision.set_execution_time((time.time() - start_time) * 1000)

# Record in trace
trace.add_decision(decision)
```

#### Results Organization

Demo results are organized in demo-specific subfolders:

```
demo/results/
├── demo1_protocol_portability/
│   ├── raw_results.json          # Complete execution results
│   ├── showcase_metrics.json      # Protocol portability key metrics
│   ├── trace_0.json              # Full decision trace with DecisionEvent
│   └── summary.txt               # Human-readable summary
├── demo2_guarantee_validation/
│   ├── raw_results.json
│   ├── showcase_metrics.json      # Guarantee validation results
│   ├── trace_0.json
│   └── summary.txt
├── demo3_concurrent_multiprotocol/
│   ├── raw_results.json
│   ├── showcase_metrics.json      # Concurrency & isolation metrics
│   ├── trace_0.json
│   └── summary.txt
├── demo4_decision_quality/
│   ├── raw_results.json
│   ├── showcase_metrics.json      # Decision quality ratings
│   ├── trace_0.json
│   └── summary.txt
├── demo5_protocol_selection/
│   ├── raw_results.json
│   ├── showcase_metrics.json      # Protocol selection accuracy
│   ├── trace_0.json
│   └── summary.txt
└── demo6_custom_events/
    ├── raw_results.json
    ├── showcase_metrics.json      # Event synchronization metrics
    ├── trace_0.json
    └── summary.txt
```

#### BaseHarness Methods

New methods for saving results:

```python
# Save complete execution data
self.save_raw_results(results: Dict) -> Path
# → demo_subfolder/raw_results.json

# Save curated metrics for this demo
self.save_showcase_metrics(metrics: Dict) -> Path
# → demo_subfolder/showcase_metrics.json

# Save all execution traces
self.save_all_traces() -> None
# → demo_subfolder/trace_*.json
```

---

## Demonstration Details

### Demo 1: Protocol Portability

**Objective**: Demonstrate that a single LLM agent can execute identical decision logic across multiple protocol domains without protocol-specific code.

#### How to Run

```bash
python -m demo.harnesses.demo1_protocol_portability
```

#### What It Tests

| Aspect | Details |
|--------|---------|
| **Protocols** | Purchase, Logistics |
| **Roles** | Buyer, Merchant |
| **Scenarios** | 2 (one per protocol) |
| **Message Count** | ~7 per scenario |
| **Test Duration** | 30-60 seconds |

#### Key Validations

✓ Both protocols reach terminal state (no enabled messages)  
✓ Zero adapter exceptions during execution  
✓ Consistent decision quality (measured 1-5)  
✓ LLM correctly interprets protocol state across domains  

#### Implementation Strategy

The harness executes the same `choose_and_bind()` function for both protocols:

```python
# Same code path for both Purchase and Logistics
async def choose_and_bind(adapter, trace, llm_client):
    enabled_messages = adapter.enabled_messages
    decision = llm_client.complete(
        messages=[{"role": "user", "content": format_state(enabled_messages)}]
    )
    msg_type = parse_decision(decision)
    await adapter.send(msg_type(...))
```

No protocol-specific conditionals; the `Adapter` interface abstracts away protocol differences.

#### Result Format

**Human-Readable** (`demo1_protocol_portability_summary.txt`):
```
Demo 1: Protocol Portability
Success Rate: 2/2 scenarios

[Scenario] purchase_buyer
  Steps: 5
  Messages: 3
  Decision Quality: 4.2/5
  Status: PASSED

[Scenario] logistics_merchant
  Steps: 7
  Messages: 4
  Decision Quality: 4.1/5
  Status: PASSED

Overall: PASSED
```

**JSON Trace** (`demo1_protocol_portability_trace_*.json`):
```json
{
  "harness": "demo1_protocol_portability",
  "scenario_id": "purchase_buyer",
  "start_time": "2026-01-29T12:34:56",
  "duration_seconds": 15.3,
  "events": [...],
  "messages": [...],
  "states": [...],
  "metrics": {
    "total_steps": 5,
    "total_messages": 3,
    "decision_quality_avg": 4.2
  }
}
```

---

### Demo 2: Guarantee Validation

**Objective**: Validate that three critical framework structural guarantees hold in real protocol execution (no mocking).

#### How to Run

```bash
python -m demo.harnesses.demo2_guarantee_validation
```

#### What It Tests

| Aspect | Details |
|--------|---------|
| **Guarantees** | Message Validity, Parameter Isolation, Role Consistency |
| **Protocols** | Purchase, Logistics |
| **Test Scenarios** | 6 validation scenarios |
| **Adapter Usage** | Real BSPL adapters with no mocking |
| **Test Duration** | 20-40 seconds |

#### Guarantees Validated

**1. Message Validity**

Every message in the enabled set:
- Conforms to declared schema
- Carries required payload attributes
- Respects message type constraints

Validates that the BSPL adapter's `enabled_store` only offers schema-conforming messages to LLM decision-making.

**2. Parameter Isolation**

Parameters remain isolated across protocol contexts:
- Purchase protocol's `orderID=PO-123` is independent of Logistics's `orderID=LG-456`
- Parameter bindings from one protocol don't contaminate another
- Each adapter instance maintains separate parameter store

Validates that agents can safely participate in multiple concurrent protocol instances.

**3. Role Consistency**

Only role-appropriate messages appear in enabled set:
- A Buyer role sees only messages it can send: `rfq`, `accept`, `reject`
- Role-inappropriate messages filtered by adapter: `quote` (Seller), `deliver` (Shipper)

Validates that role context is properly enforced by the BSPL adapter.

#### Implementation Strategy

```python
# No mocking - real BSPL adapters
adapter = Adapter(Buyer, systems, agents)  # Real adapter instance

# Inspect enabled messages
enabled = adapter.enabled_messages
assert all(msg.conforms_to_schema() for msg in enabled)
assert all(msg in Buyer.sendable_messages() for msg in enabled)

# Serialize and inspect state
state = serialize_adapter_state(adapter)
assert "orderID" not in state  # Not bound yet
```

#### Result Format

**Human-Readable** (`demo2_guarantee_validation_summary.txt`):
```
Demo 2: Guarantee Validation
All Guarantees: PASSED

Message Validity Guarantee
  Purchase Protocol: ✓ PASSED
  Logistics Protocol: ✓ PASSED
  Detail: All 12 enabled messages conform to schema

Parameter Isolation Guarantee
  Isolation Status: ✓ PASSED
  Purchase orderID: Independent
  Logistics orderID: Independent
  Cross-contamination: None detected

Role Consistency Guarantee
  Purchase Buyer: ✓ PASSED
  Logistics Merchant: ✓ PASSED
  Detail: 0 role-inappropriate messages in enabled sets
```

**JSON Trace** (`demo2_guarantee_validation_trace_*.json`):
```json
{
  "guarantees": {
    "message_validity": {
      "status": "PASSED",
      "enabled_messages_count": 12,
      "invalid_messages": 0
    },
    "parameter_isolation": {
      "status": "PASSED",
      "purchase_params": {...},
      "logistics_params": {...},
      "cross_contamination": false
    },
    "role_consistency": {
      "status": "PASSED",
      "buyer_messages": ["rfq", "accept", "reject"],
      "inappropriate_messages": 0
    }
  }
}
```

---

### Demo 3: Concurrent Multiprotocol Participation

**Objective**: Demonstrate that agents can safely participate in multiple protocol instances simultaneously with proper parameter isolation and state management.

#### How to Run

```bash
python -m demo.harnesses.demo3_concurrent_multiprotocol
```

#### What It Tests

| Aspect | Details |
|--------|---------|
| **Protocols** | Purchase + Logistics (concurrent) |
| **Roles** | Buyer + Merchant (simultaneous) |
| **Scenarios** | 3 (2 single-protocol, 1 dual-protocol) |
| **Concurrent Adapters** | 2+ running simultaneously |
| **Message Interleaving** | LLM decisions from multiple protocol states |
| **Test Duration** | 45-90 seconds |

#### Key Validations

✓ Both protocol instances reach terminal state  
✓ Parameter bindings remain isolated (Purchase orderID ≠ Logistics orderID)  
✓ Message decisions reflect correct protocol context  
✓ No state leakage between adapter instances  
✓ Concurrent async operations complete correctly  

#### Implementation Strategy

The harness runs multiple adapters concurrently:

```python
# Create two independent adapter instances
purchase_adapter = Adapter(Buyer, systems, agents)
logistics_adapter = Adapter(Merchant, systems, agents)

# Run both concurrently
results = await asyncio.gather(
    run_adapter(purchase_adapter, "purchase_buyer"),
    run_adapter(logistics_adapter, "logistics_merchant")
)

# Verify isolation: parameters didn't cross
assert purchase_state["orderID"] != logistics_state["orderID"]
```

#### Result Format

**Human-Readable** (`demo3_concurrent_multiprotocol_summary.txt`):
```
Demo 3: Concurrent Multiprotocol
Success Rate: 3/3 scenarios

[Scenario] purchase_then_logistics (sequential)
  Purchase Buyer: 5 steps, PASSED
  Logistics Merchant: 7 steps, PASSED
  Status: PASSED

[Scenario] concurrent_execution (simultaneous)
  Purchase Buyer: 5 steps ⎤
  Logistics Merchant: 7 steps ⎥ (concurrent)
  State Isolation: ✓
  Parameter Contamination: None
  Status: PASSED
```

**JSON Trace** (`demo3_concurrent_multiprotocol_trace_*.json`):
```json
{
  "execution_mode": "concurrent",
  "purchase_adapter_id": "adapter_001",
  "logistics_adapter_id": "adapter_002",
  "isolation_metrics": {
    "parameter_contamination_events": 0,
    "state_divergence": 0,
    "concurrent_message_ordering_violations": 0
  },
  "concurrency_stats": {
    "max_concurrent_adapters": 2,
    "total_interleaved_decisions": 12,
    "total_duration_seconds": 52.3
  }
}
```

---

### Demo 4: Decision Quality Evaluation

**Objective**: Evaluate the semantic appropriateness of LLM decisions across protocol states using human-comparable 1-5 ratings.

#### How to Run

```bash
python -m demo.harnesses.demo4_decision_quality
```

#### What It Tests

| Aspect | Details |
|--------|---------|
| **Protocols** | Purchase, Logistics |
| **Evaluation Criteria** | Semantic appropriateness (1-5 scale) |
| **Scenarios** | 2 (one per protocol) |
| **Decision Points** | ~10-15 per scenario |
| **Test Duration** | 60-120 seconds |

#### Quality Dimensions Evaluated

- **Appropriateness** (1-5): Does the chosen message fit the current state?
- **Progression** (1-5): Does the decision move toward protocol completion?
- **Consistency** (1-5): Does the decision align with previous choices?
- **Robustness** (1-5): Would the decision work across protocol variations?

#### Result Format

**Human-Readable** (`demo4_decision_quality_summary.txt`):
```
Demo 4: Decision Quality
Quality Ratings: COMPREHENSIVE

[Scenario] purchase_buyer
  Decision 1 (rfq): Appropriateness=5, Progression=5, Consistency=5
  Decision 2 (accept): Appropriateness=4, Progression=4, Consistency=5
  Decision 3 (reject): Appropriateness=4, Progression=4, Consistency=4
  Average Quality: 4.3/5

[Scenario] logistics_merchant
  Average Quality: 4.2/5

Overall Average: 4.25/5
Quality Status: GOOD
```

---

### Demo 5: Protocol Selection

**Objective**: Evaluate the accuracy of user intent → protocol/role mapping.

#### How to Run

```bash
python -m demo.harnesses.demo5_protocol_selection
```

#### What It Tests

| Aspect | Details |
|--------|---------|
| **Input** | User intent descriptions |
| **Output** | Selected protocol + role |
| **Accuracy Target** | 100% correct mapping |
| **Test Scenarios** | 10+ intent examples |
| **Test Duration** | 30-60 seconds |

#### Sample Intents

- "I want to buy office supplies" → Purchase/Buyer
- "I need to organize package wrapping" → Logistics/Merchant
- "I'm selling software licenses" → Purchase/Seller

#### Result Format

**Human-Readable** (`demo5_protocol_selection_summary.txt`):
```
Demo 5: Protocol Selection
Accuracy: 10/10 (100%)

Intent 1: "I want to buy office supplies"
  Selected: Purchase / Buyer
  Correct: YES ✓
  Confidence: 0.98

Intent 2: "I'm organizing package delivery"
  Selected: Logistics / Merchant
  Correct: YES ✓
  Confidence: 0.95

...

Overall Accuracy: 100%
Status: PASSED
```

---

### Demo 6: Custom LLM Events

**Objective**: Demonstrate concurrent execution of protocol adapter reactions and custom business logic events using unified LLM decision-making.

#### How to Run

```bash
python -m demo.harnesses.demo6_custom_events
```

#### What It Tests

| Aspect | Details |
|--------|---------|
| **Event Types** | Protocol reactions + custom events |
| **Synchronization** | asyncio.Lock for serialized decisions |
| **Scenarios** | 2 (timeout-based, stall detection) |
| **Concurrent Tasks** | 2-3 running simultaneously |
| **Test Duration** | 30-60 seconds |

#### Event Types Demonstrated

**Protocol Events** (Adapter Reactions):
- Triggered by incoming messages from other participants
- Use `@adapter.reaction(MessageType)` decorator
- Synchronize via shared lock for LLM decision-making

**Custom Events** (Business Logic):
- Triggered by timeouts, checks, business rules
- Use manual polling or event handlers
- Same `choose_and_bind()` decision logic
- Synchronized with adapter reactions via lock

#### Implementation Pattern

```python
# Shared lock for decision serialization
decision_lock = asyncio.Lock()

# Protocol reaction (adapter-driven)
@adapter.reaction(IncomingMessage)
async def on_message(msg):
    async with decision_lock:
        await choose_and_bind(adapter, llm_client)

# Custom event (business-driven)
async def periodic_check():
    while running:
        await asyncio.sleep(2)
        async with decision_lock:
            await choose_and_bind(adapter, llm_client)

# Run concurrently
await asyncio.gather(
    adapter.run(),
    periodic_check()
)
```

#### Result Format

**Human-Readable** (`demo6_custom_events_summary.txt`):
```
Demo 6: Custom LLM Events
Event Synchronization: PASSED

[Scenario] purchase_with_timeout
  Adapter Decisions: 3
  Custom Decisions: 2
  Total LLM Calls: 5
  Lock Acquisitions: 5 (no conflicts)
  Synchronization Status: ✓ PASSED

[Scenario] logistics_with_stall_detection
  Adapter Decisions: 4
  Custom Decisions: 1
  Total LLM Calls: 5
  Lock Acquisitions: 5 (no conflicts)
  Synchronization Status: ✓ PASSED

Overall: PASSED
Success Rate: 2/2
Total Concurrent Events: 5
Synchronization Violations: 0
```

**JSON Trace** (`demo6_custom_events_trace_*.json`):
```json
{
  "event_log": [
    {
      "timestamp": "2026-01-29T12:34:56.001",
      "event_type": "adapter_reaction",
      "message_type": "IncomingQuote",
      "decision": "accept",
      "llm_call_id": "call_001"
    },
    {
      "timestamp": "2026-01-29T12:34:58.234",
      "event_type": "custom_timeout_check",
      "check": "has_quote_arrived",
      "decision": "send_reminder",
      "llm_call_id": "call_002"
    }
  ],
  "synchronization_metrics": {
    "total_lock_acquisitions": 5,
    "max_lock_wait_time_ms": 0.3,
    "synchronization_violations": 0
  }
}
```

---

## Testing Framework

The demonstration suite includes comprehensive pytest tests for each demo:

| Demo | Test File | Tests | Focus |
|------|-----------|-------|-------|
| 1 | `test_demo1_protocol_portability.py` | 47 | Protocol-agnostic execution |
| 2 | `test_demo2_guarantee_validation.py` | 54 | Structural guarantees |
| 3 | `test_demo3_concurrent_multiprotocol.py` | 53 | Concurrent multi-protocol |
| 6 | `test_demo6_custom_events.py` | 41 | Event synchronization |

Run tests:
```bash
pytest demo/tests/ -v
```

---

## Directory Structure

```
demo/
├── harnesses/
│   ├── base_harness.py                      # Core infrastructure
│   ├── demo1_protocol_portability.py
│   ├── demo2_guarantee_validation.py
│   ├── demo3_concurrent_multiprotocol.py
│   ├── demo4_decision_quality.py
│   ├── demo5_protocol_selection.py
│   ├── demo6_custom_events.py
│   ├── master_harness.py                    # Orchestrator
│   ├── DEMO1.md, DEMO2.md, ..., DEMO6.md   # Detailed docs
│   └── __init__.py
├── tests/
│   ├── test_demo1_protocol_portability.py
│   ├── test_demo2_guarantee_validation.py
│   ├── test_demo3_concurrent_multiprotocol.py
│   ├── test_demo6_custom_events.py
│   ├── pytest.ini
│   ├── test-requirements.txt
│   └── TESTREADME.md
├── results/                                  # Auto-generated outputs
├── README.md                                 # Quick reference
└── DEMOREADME.md                            # This file
```

---

## Performance Characteristics

| Demo | Typical Duration | LLM Calls | Memory Usage |
|------|------------------|-----------|--------------|
| 1 | 30-60s | 10-12 | ~50 MB |
| 2 | 20-40s | 6-8 | ~40 MB |
| 3 | 45-90s | 15-20 | ~80 MB |
| 4 | 60-120s | 15-20 | ~60 MB |
| 5 | 30-60s | 10-15 | ~50 MB |
| 6 | 30-60s | 10-12 | ~60 MB |
| **All** | **3-6 min** | **66-87** | **~100 MB** |

---

## Troubleshooting

### Common Issues

**Demo hangs (timeout)**
- Check ANTHROPIC_API_KEY environment variable
- Verify network connectivity to Claude API
- Increase timeout if network is slow

**Adapter initialization fails**
- Verify `protocols/*.bspl` files exist
- Check `configuration.py` loads all protocols
- Ensure protocol syntax is valid

**Results not saved**
- Verify `demo/results/` directory is writable
- Check available disk space
- Ensure file permissions are correct

### Enabling Debug Logging

Set environment variable:
```bash
export DEBUG=1
pytest demo/tests/ -v -s --log-cli-level=DEBUG
```

---

## Citation

If using these demonstrations in research, please cite the AHOY paper:

```bibtex
@article{ahoy2026,
  title={AHOY: LLMs Enacting Multiagent Interaction Protocols},
  year={2026}
}
```

**Test Cases**: 4

### Demo 3: Concurrent Multiprotocol Participation

**Goal**: Simultaneous multi-protocol execution with state isolation

**Test Scenarios**: 1 (Purchase + Logistics in parallel)

**Validates**:
- Parameter isolation
- Message history separation
- Coherent decisions per protocol
- Zero cross-protocol contamination
- Independent termination

### Demo 4: Decision Quality Across Domains

**Goal**: Evaluate semantic appropriateness of decisions

**Test Scenarios**: 4 domain-specific decision points
- Price negotiation (Purchase)
- Material selection (Logistics)
- Offer rejection (Purchase)
- Shipping priority (Logistics)

**Success Criterion**: Average score  3.5/5.0

### Demo 5: Protocol Selection Accuracy

**Goal**: Map user intent to protocol/role

**Test Cases**: 13 diverse inputs
- Easy (4): Clear intent "I want to buy a notebook"
- Medium (2): Implied roles
- Hard (5): Ambiguous "I want to ship something"
- Complex (2): Multi-agent scenarios

**Success Criteria**:
- Overall accuracy  80%
- Easy: 100%
- Hard:  75%

**Output**: CSV results + accuracy metrics

## Output & Results

### Result Files

After execution, check demo/results/:

``
master_report.json                          # Unified summary
demo1_protocol_portability.log              # Execution log
demo1_protocol_portability_summary.txt      # Human-readable summary
demo1_protocol_portability_trace_*.json     # Detailed traces
... (similar for demos 2-5)
demo5_protocol_selection_results.csv        # Analysis-ready CSV
``

### Viewing Results

``Bash
# Master report
cat demo/results/master_report.json | python -m json.tool

# Individual demo summary
cat demo/results/demo1_protocol_portability_summary.txt

# Execution log
cat demo/results/demo1_protocol_portability.log

# Protocol selection results
head -20 demo/results/demo5_protocol_selection_results.csv
``

## Success Criteria

| Demo | Criterion |
|------|-----------|
| 1 | All protocols complete, zero violations |
| 2 | All guarantees pass |
| 3 | State isolation maintained, zero contamination |
| 4 | Average score  3.5/5.0 |
| 5 | Accuracy  80%, easy 100%, hard  75% |

## Extending

### Adding Test Cases

Edit test case definitions in harness classes (defined as data, not code):

``python
self.test_scenarios = [
    {
        'id': 'scenario_1',
        'protocol': 'Purchase',
        'role': 'Buyer',
        ...
    }
]
``

### Adding a New Demo

1. Create demo_N_<name>.py in harnesses/
2. Inherit from BaseHarness
3. Implement async def run(self)
4. Add to MasterHarness
5. Update __init__.py

## Troubleshooting

**LLM API errors**
- Check ANTHROPIC_API_KEY environment variable
- Verify network connectivity

**Adapter initialization fails**
- Verify protocols/*.bspl files exist
- Check configuration.py loads protocols

**Traces not saved**
- Verify demo/results/ is writable
- Check disk space

## Code Statistics

| Metric | Value |
|--------|-------|
| Implementation Lines | ~2,190 |
| Test Cases | 24 |
| Architecture | 3 layers (Base  Individual  Master) |

## Status

 **IMPLEMENTATION COMPLETE**

- All 5 demos fully implemented
- Production-ready with error handling
- 24 test cases
- Reproducible execution traces
- Ready for paper results
