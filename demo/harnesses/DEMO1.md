# Demo 1: Protocol Portability - Implementation Guide

## Overview

Demo 1 tests protocol portability by executing identical agent code across two different protocols:
- **Purchase Protocol**: Buyer role
- **Logistics Protocol**: Merchant role

The same `choose_and_bind()` function and `adapter.send()` calls execute both scenarios without protocol-specific code branches.

## Running the Demo

### Basic Execution
```bash
python -m demo.harnesses.demo1_protocol_portability
```

### With Logging
```bash
python -m demo.harnesses.demo1_protocol_portability 2>&1 | tee demo1_output.log
```

### Expected Output
```
Demo 1: Protocol Portability - Starting
Testing: Same agent logic across multiple protocols
======================================================================

[Scenario] purchase_buyer
  Protocol: Purchase
  Role: Buyer
  Goal: Buy a pen for less than $10
  ✓ Success: 5 steps, 3 messages sent

[Scenario] logistics_merchant
  Protocol: Logistics
  Role: Merchant
  Goal: Organize the wrapping and labeling of packages
  ✓ Success: 7 steps, 4 messages sent

======================================================================
Demo 1: Protocol Portability - Complete
Success Rate: 2/2
Total Steps Executed: 12
Total Messages Sent: 7
Violations Detected: 0
```

---

## How the Demo Code Works

### Architecture

The demo follows a standard execution flow:

```
Load Protocol Config
    ↓
Create BSPL Adapter
    ↓
Check Enabled Messages
    ↓
Call choose_and_bind() for LLM Decision
    ↓
Send Message via adapter.send()
    ↓
Advance Protocol State
    ↓
Repeat until Terminal State (no enabled messages)
```

### Core Execution Flow (run_protocol_enactment method)

**STEP 1: Load Protocol Configuration**
```python
system_config = systems[protocol_name]
protocol_obj = system_config["protocol"]
role_obj = protocol_obj.roles[role_name]
```
Retrieves protocol and role objects from configuration.

**STEP 2: Create Real BSPL Adapter**
```python
adapter = Adapter(role_obj, systems, agents)
```
Instantiates the BSPL adapter that manages protocol state machine and message validation.

**STEP 3: Decision Loop**
```python
while step_count < max_steps:
    enabled_store = adapter.enabled_store
    enabled_messages = list(enabled_store.messages())
    
    if not enabled_messages:
        break  # Protocol reached terminal state
```
Checks what messages are legally allowed to send at current protocol state.

**STEP 4: LLM Decision**
```python
message_instance = await choose_and_bind(
    adapter=adapter,
    enabled_store=enabled_store,
    event={"type": "decision_step", "step": step_count},
    client=self.llm_client,
    timeout=30.0,
    agent_name=f"{protocol_name}:{role_name}"
)
```
Calls production LLM function to select and bind message parameters. This is identical for both protocols.

**STEP 5: Message Sending**
```python
try:
    await adapter.send(message_instance)
    messages_sent += 1
    trace.add_message(msg_type=message_instance.schema.name, ...)
except Exception as e:
    trace.add_error("message_send_error", str(e), {...})
    adapter_exceptions += 1
    break
```
Actually sends message through adapter (validates schema). Adapter raises exception if message violates protocol constraints.

**STEP 6: Metrics Compilation**
```python
return {
    "status": "success",
    "steps_executed": step_count,
    "messages_sent": messages_sent,
    "adapter_exceptions": adapter_exceptions,
    "violations": len(trace.errors),
    "terminal_reached": step_count < max_steps,
}
```
Returns structured results with execution metrics.

---

## Violation Tracking

### How Violations Are Detected

Violations are caught at multiple points:

#### 1. LLM Decision Errors
```python
try:
    message_instance = await choose_and_bind(...)
except Exception as e:
    trace.add_error("llm_decision_error", str(e), {
        "step": step_count,
        "enabled_count": len(enabled_messages)
    })
    adapter_exceptions += 1
```
Records if LLM decision function fails (timeout, API error, invalid response).

#### 2. Message Schema Violations
```python
try:
    await adapter.send(message_instance)
except Exception as e:
    trace.add_error("message_send_error", str(e), {
        "step": step_count,
        "message_type": message_instance.schema.name
    })
    adapter_exceptions += 1
```
BSPL adapter raises exception if:
- Required parameters missing
- Parameter types incorrect
- Message preconditions not met
- Message ordering violates protocol rules

#### 3. Configuration Errors
```python
except KeyError as e:
    error_msg = f"Invalid protocol/role: {protocol_name}/{role_name}"
    trace.add_error("invalid_configuration", error_msg, {
        "available_protocols": list(systems.keys())
    })
```
Catches invalid protocol or role names.

### How Violations Are Tracked

#### ExecutionTrace Object
```python
trace = self.create_trace(scenario_id)

# Record events
trace.add_event("adapter_created", {...})
trace.add_event("protocol_terminal", {...})

# Record messages
trace.add_message(msg_type="RequestWrapping", sender="Merchant", receiver="other", payload={...})

# Record state snapshots
trace.add_state_snapshot(protocol_name, role_name, social_state)

# Record errors/violations
trace.add_error("message_send_error", "Parameter X missing", {...})
```

#### Violation Metrics
```python
violations = len(trace.errors)  # Count of all errors recorded
adapter_exceptions += 1         # Count when caught
```

#### Final Results
```python
{
    "violations": len(trace.errors),          # Total errors
    "adapter_exceptions": adapter_exceptions,  # Adapter-level errors
    "terminal_reached": step_count < max_steps # Protocol completion
}
```

### Checking for Constraint Violations

**In Results**: `violations == 0` means no constraint violations  
**In Logs**: Check execution trace for `add_error()` calls  
**In Debug**: Each error includes context (step, message type, error message)

---

## Maintaining the Code

### Class Structure

```python
class ProtocolPortabilityHarness(BaseHarness):
    def __init__(self):
        """Initialize with test scenarios"""
        
    async def run_protocol_enactment(self, protocol_name, role_name, agent_goal, trace, max_steps):
        """Execute single protocol enactment"""
        
    async def run(self):
        """Orchestrate all scenarios and aggregate results"""
```

### Key Dependencies

| Dependency | Purpose | Location |
|------------|---------|----------|
| `Adapter` | BSPL protocol state machine | `bspl.adapter` |
| `choose_and_bind()` | LLM decision function | `lib.llm_client` |
| `extract_social_state()` | Current protocol state | `lib.state_manager` |
| `ExecutionTrace` | Execution tracking | `base_harness` |
| `AnthropicLLMClient` | LLM client | `lib.llm_client` |
| `systems` | Protocol configuration | `configuration` |

### Adding New Test Scenarios

To add a scenario, add to `self.test_scenarios` in `__init__()`:

```python
{
    "id": "scenario_id",
    "protocol": "ProtocolName",
    "role": "RoleName",
    "description": "What this scenario tests",
    "agent_goal": "Natural language goal"
}
```

The same `run_protocol_enactment()` code will execute the new scenario without modification.

### Modifying Protocol Selection

To test different protocol-role pairs, modify `test_scenarios` dictionary. All other code remains unchanged (demonstrating protocol portability).

### Updating Error Handling

Error types can be extended in `run_protocol_enactment()`:

```python
try:
    # operation
except SpecificError as e:
    trace.add_error("new_error_type", str(e), {"context": {...}})
```

Each error type is tracked separately in results.

### Performance Tuning

**max_steps parameter**: Controls maximum decision loops per scenario (safety limit)  
**timeout parameter**: Controls LLM call timeout (in choose_and_bind)  
**Modify in**: `run_protocol_enactment()` method call

```python
scenario_results = await self.run_protocol_enactment(
    protocol_name=scenario['protocol'],
    role_name=scenario['role'],
    agent_goal=scenario['agent_goal'],
    trace=trace,
    max_steps=10  # Change this value
)
```

---

## Code Organization

### File: demo1_protocol_portability.py

**Lines 1-23**: Module docstring  
**Lines 45-68**: Class and test scenarios  
**Lines 70-240**: `run_protocol_enactment()` - Core execution  
**Lines 242-340**: `run()` - Orchestration and results aggregation  
**Lines 343-355**: `main()` - Entry point  

### Key Methods

**run_protocol_enactment()**
- Executes single protocol scenario
- Returns per-scenario metrics
- Records execution trace

**run()**
- Iterates through all scenarios
- Aggregates results
- Computes summary statistics
- Saves traces

### Step Comments in Code

```python
# === STEP 1: Load protocol configuration ===
# === STEP 2: Create real BSPL adapter ===
# === STEP 3: Execute decision loop ===
# === STEP 4: Use actual choose_and_bind() for LLM decision ===
# === STEP 5: Validate and send message ===
# === STEP 6: Compile execution metrics ===
```

Each STEP has clear start/end markers for navigation.

---

## Related Files

### Base Infrastructure
- **base_harness.py** - Provides `BaseHarness` class with `ExecutionTrace` and trace management
- **configuration.py** - Protocol definitions and system configuration
- **__init__.py** - Package initialization

### Protocol Definitions
- **protocols/purchase.bspl** - Purchase protocol specification
- **protocols/logistics.bspl** - Logistics protocol specification

### Supporting Libraries
- **lib/llm_client.py** - `choose_and_bind()` and LLM client
- **lib/state_manager.py** - `extract_social_state()`
- **lib/protocol_discovery.py** - Protocol metadata utilities

### Results and Logs
- **demo/results/protocol_portability/** - Execution traces saved here
- Logs during execution print to console and file

---

## Understanding the Results

### Metrics Returned

```python
{
    "status": "success" | "error",
    "protocol": "Purchase" | "Logistics",
    "role": "Buyer" | "Merchant",
    "steps_executed": int,           # Number of decision loops
    "messages_sent": int,             # Actual messages sent
    "decisions_made": int,            # LLM decisions made
    "adapter_exceptions": int,        # Adapter-level errors
    "terminal_reached": bool,         # Did protocol finish
    "violations": int,                # Constraint violations detected
    "execution_time_seconds": float
}
```

### Success Criteria

Protocol portability is validated when:
- ✅ `violations == 0` (no constraint violations)
- ✅ `adapter_exceptions == 0` (no protocol errors)
- ✅ `terminal_reached == True` (protocol completed)
- ✅ `messages_sent > 0` (actually executed)
- ✅ Both scenarios succeed

### Checking Results

**Pass**: Both scenarios return `status: "success"` with `violations: 0`  
**Fail**: Either scenario returns `status: "error"` or has violations  
**Incomplete**: Protocol didn't reach terminal state (infinite loop or early termination)

---

## Debugging

### Common Issues

**Issue**: "No enabled messages" at step 1
- Check: Is the initial protocol state valid?
- Fix: Verify protocol definition in configuration.py

**Issue**: "LLM decision error"
- Check: Is LLM client configured correctly?
- Check: Are API credentials valid?
- Fix: Review error message context in trace

**Issue**: "message_send_error"
- Check: Are message parameters correct?
- Check: Review trace for parameter bindings
- Fix: Verify message schema in protocol definition

**Issue**: "violations > 0"
- Check: Which constraint failed? (in error details)
- Check: What was the message that caused violation?
- Fix: Review protocol rules and message ordering

### Accessing Execution Traces

Traces are saved to: `demo/results/protocol_portability/traces/`

Each trace file contains:
- `events`: Protocol state changes
- `messages`: Messages sent
- `states`: Protocol state snapshots
- `errors`: All violations and exceptions
- `metrics`: Performance data

Load trace:
```python
import json
with open('demo/results/protocol_portability/traces/scenario_id.json') as f:
    trace = json.load(f)
```

---

## Key Implementation Details

### Why No Protocol-Specific Code?

The code achieves protocol portability through:
1. **Single `choose_and_bind()` call** - Works with any protocol
2. **Generic adapter handling** - Adapter encapsulates protocol differences
3. **Event-driven execution** - Protocol state drives loop, not hardcoded logic
4. **Parameterized scenarios** - Same code, different test data

### How Adapter Enforces Constraints

```python
# Adapter manages enabled messages
enabled_messages = list(adapter.enabled_store.messages())

# Only legal messages offered to LLM
# Adapter raises exception if send() violates rules
await adapter.send(message_instance)
```

BSPL adapter validates:
- Message schema conformance
- Parameter bindings
- Message preconditions
- Protocol state machine transitions

### Message Flow

```
Enabled Messages (from adapter)
    ↓
LLM selects one via choose_and_bind()
    ↓
Message instance created with bindings
    ↓
adapter.send() validates and sends
    ↓
Protocol state advances
    ↓
New enabled messages computed
```

---

## Summary

**Demo 1 validates protocol portability by**:
- Executing identical code for two different protocols
- Tracking all violations through ExecutionTrace
- Using BSPL adapter to enforce constraints
- Achieving zero violations when run correctly

**To modify or extend**:
- Change test scenarios in `__init__()`
- Adjust execution parameters in `run_protocol_enactment()`
- Add error types via `trace.add_error()`
- Same core code handles all variations
