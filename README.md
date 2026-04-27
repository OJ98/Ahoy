# Ahoy: Multi-Agent Framework for Intelligent BSPL Protocol Enactment

A research system demonstrating LLM-driven agents coordinating through formally-specified BSPL (Blindingly Simple Protocol Language) protocols. Supports multiple protocol enactments with protocol-agnostic LLM decision-making.

## Project Structure

```
├── chips.py                    # Interactive protocol/role setup interface
├── configuration.py            # Protocol loading and system initialization
├── start.ps1 / start.sh        # Multi-agent orchestration scripts
├── input.txt                   # User requirements (system + user prompts)
├── requirements.txt            # Python dependencies
│
├── agents/                     # Agent implementations
│   ├── ahoy.py                # Generic LLM-driven agent (protocol-agnostic)
│   ├── buyer.py, seller.py    # Purchase protocol agents
│   ├── merchant.py, wrapper.py # Logistics protocol agents
│   └── logs/                  # Per-agent logs and notes
│
├── lib/                        # Core libraries
│   ├── llm_client.py          # Anthropic API client + prompt helpers
│   ├── state_manager.py       # BSPL adapter state serialization
│   ├── protocol_discovery.py  # Protocol introspection
│   ├── agent_notes.py         # Lightweight persistent notes
│   ├── utils.py               # Prompt building and shutdown
│   └── dynamic_adapter_manager.py  # Multi-protocol coordination
│
├── protocols/                  # BSPL protocol specifications
│   ├── purchase.bspl          # E-commerce (Buyer, Seller, Shipper)
│   ├── logistics.bspl         # Supply chain (Merchant, Wrapper, Labeler, Packer)
│   ├── credit_purchase.bspl   # Credit-based variant
│   └── protocol_descriptions.txt  # Human-readable descriptions
│
└── tests/                      # pytest test suite
    ├── test_configuration.py   # Protocol loading
    ├── test_state_manager.py   # State serialization
    ├── test_protocol_discovery.py  # Protocol introspection
    └── conftest.py             # Shared fixtures
```

## Quick Start

### 1. Setup Environment

```bash
# Install Python dependencies
pip install -r requirements.txt

# Ensure ANTHROPIC_API_KEY is set
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 2. Interactive Setup (Recommended)

```bash
python chips.py
```

The `chips.py` interface converses with you to infer protocol and role, then generates `input.txt` with your scenario as the system prompt.

### 3. Run All Agents

```powershell
# Windows
./start.ps1

# Unix/Linux
./start.sh
```

Each agent runs in a separate process, coordinating via BSPL message passing. Logs are collected in `logs/agents.log`.

### 4. Run Single Agent (Testing)

```bash
python agents/ahoy.py  # Generic LLM agent with auto-detected protocol/role
python agents/buyer.py # Direct role-specific agent
```

## Running the Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=lib --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_configuration.py -v

# Run tests matching a pattern
pytest tests/ -k "protocol" -v
```

## System Architecture

### Protocol-Agnostic LLM Agent (Single or Multiple)

The system uses a **hybrid approach**: a generic LLM agent (`ahoy.py`) dynamically adapts to any protocol, supporting both single and **multiple roles in parallel**.

```
User Input
    ↓
CHIPS Interface (Protocol/Role Inference)
    ↓
LLM-Selected Protocol + Role(s)
    ↓
Multiple Generic Adapters (One per Role)
    ↓
Concurrent BSPL Protocol Interaction
    ↓
Shared LLM Decision-Making (Multi-Protocol Aware)
```

### Single Agent Mode
One role coordinates protocol enactment:
```python
assigned_roles_list = [('Purchase', 'Buyer')]
adapter = create_adapter_for_role('Purchase', 'Buyer')
adapter.decision()(llm_decision_handler)
adapter.start()
```

### Multi-Agent Mode (Parallel)
Multiple roles run concurrently with shared LLM coordination:
```python
assigned_roles_list = [('Purchase', 'Buyer'), ('Logistics', 'Merchant')]
# Create adapters for each role
for protocol, role in assigned_roles_list:
    adapters[f"{protocol}:{role}"] = create_adapter_for_role(protocol, role)

# Register multi-protocol decision handler with each adapter
for adapter_key, adapter_instance in adapters.items():
    multi_handler = _get_multi_protocol_decision_handler(adapter_key)
    adapter_instance.decision()(multi_handler)

# Start all adapters concurrently
asyncio.gather(*[a.start() for a in adapters.values()])
```

**Key Design Features**:

1. **Protocol-Agnostic**: No role-specific implementations needed
2. **Parallel Execution**: Multiple roles coordinate via shared LLM decision-making
3. **Automatic Role Detection**: CHIPS infers single or multiple roles from user input
4. **Shared LLM Context**: Multi-protocol scenarios provide all adapters' states to LLM
5. **Graceful Coordination**: Each agent has:
   - A unique **claimed role** stored in `%TEMP%/maf_claimed_role_{PID}.txt`
   - Access to the **stop signal** at `%TEMP%/maf_stop_signal.txt` for graceful shutdown
   - A **message history** tracking protocol state via `state_manager.py`

### Protocol Loading & Message Types

```python
# In configuration.py
from bspl import load_file

purchase_spec = load_file("protocols/purchase.bspl")
purchase_protocol = purchase_spec.protocols["Purchase"]
purchase_spec.export("Purchase")  # Creates importable module
from Purchase import Buyer, Seller, RequestToBuy, Quote  # Message types
```

Each BSPL protocol is loaded once and exported as a Python module, making message types available for type-safe reactions:

```python
@adapter.reaction(RequestToBuy)
async def handle_rfq(msg):
    """Triggered when RequestToBuy message is available."""
    await adapter.send(Quote(price=50, **msg.payload))
    return msg
```

### Adapter Reactions & Message Handling

Agents use the `@adapter.reaction(MessageType)` decorator to define message handlers:

```python
from Logistics import RequestWrapping, Wrapped
from bspl.adapter import Adapter

adapter = Adapter(Wrapper, systems, agents)

@adapter.reaction(RequestWrapping)
async def wrap(msg):
    """Process wrapping requests with material selection."""
    wrapping = "bubblewrap" if msg["item"] in ["plate", "glass"] else "paper"
    await adapter.send(Wrapped(wrapping=wrapping, **msg.payload))
    return msg
```

**Key Points**:
- `@adapter.reaction(MessageType)`: Triggered when message **is available** (non-blocking)
- `@adapter.enabled(MessageType)`: Triggered when message **CAN be sent** (preconditions met)
- Always `return msg` or `await adapter.send(response)` to maintain protocol state
- Message access via dict-like syntax: `msg["field"]` or `msg.payload`

## Core Modules

### `llm_client.py` - LLM Communication

**LLM Call Tracking**:
- Max calls: 20 per session (configurable)
- Max duration: 180 seconds (configurable)
- Tracks all calls centrally via `LLMCallTracker`

```python
from lib.llm_client import initialize_llm_tracker, get_llm_tracker

tracker = initialize_llm_tracker(max_calls=20, max_duration_seconds=180)
# ... later ...
exceeded, reason = tracker.check_threshold_exceeded()
if exceeded:
    raise SystemExit(f"Threshold: {reason}")
```

**Main API**:
```python
from lib.llm_client import AnthropicLLMClient

llm = AnthropicLLMClient(model="claude-haiku-4-5-20251001")
response = await llm.complete(
    prompt="Your decision prompt",
    system_prompt="System context",
    max_tokens=1000
)
```

### `state_manager.py` - Protocol State Serialization

Extracts BSPL adapter state into JSON for LLM context. Handles:
- Message bindings and payloads
- Protocol metadata (roles, constraints)
- System contexts (nested bindings)
- Message history (timestamps, senders, recipients)

```python
from lib.state_manager import extract_social_state

social_state = extract_social_state(adapter)
# Returns:
# {
#   "adapter_name": "Merchant",
#   "timestamp": "2026-02-02T10:30:45.123456",
#   "systems": {
#     "system_1": {
#       "root_context": {...},
#       "all_messages": [{schema_name, payload, sender, recipients, ...}],
#       "message_count": 3
#     }
#   },
#   "global_message_count": 5,
#   "protocols": ["Logistics"],
#   "roles": ["Merchant", "Wrapper"]
# }
```

### `protocol_discovery.py` - Protocol Introspection

Analyzes BSPL protocol structures to extract roles, messages, and descriptions:

```python
from lib.protocol_discovery import (
    get_all_protocols,
    get_protocol_structure,
    get_protocol_summary_for_llm,
    validate_protocol_and_role
)

protocols = get_all_protocols()  # {"Purchase": ..., "Logistics": ...}
structure = get_protocol_structure("Purchase")
# Returns: {name, roles: [Buyer, Seller, Shipper], messages: [...]}

summary = get_protocol_summary_for_llm()
# Returns formatted string for LLM context

validate_protocol_and_role("Purchase", "Buyer")  # Raises if invalid
```

### `event_injector.py` - External Event Injection

Interface for external systems (inventory management, market data feeds) to inject events into running agents without modifying agent code.

**Usage**:
```python
from lib.event_injector import post_event_to_agent

# Inject an event
post_event_to_agent(
    event_type="user_defined",
    message="Purchase request: Buy a widget",
    priority="high",
    metadata={"item": "widget", "delivery_address": "...", "budget": 99.99},
    protocol_name="Purchase",
    role="Buyer"
)
```

### `termination_condition_manager.py` - Protocol Termination Tracking

Generates and tracks termination conditions for protocol transactions. Monitors when protocol requirements are satisfied:

**Capabilities**:
- Tracks event metadata and user requirements
- Specifies required protocol messages for completion
- Monitors progress toward completion
- Generates termination criteria based on protocol completion rules

```python
from lib.termination_condition_manager import (
    get_termination_condition_file,
    get_termination_history_file
)

# Access termination tracking files
condition_file = get_termination_condition_file()
history_file = get_termination_history_file()
```

### `agent_notes.py` - Persistent Agent Memory

Lightweight key-value store for agents to save state across decisions. Notes reset each run:

```python
from lib.agent_notes import get_agent_notes

notes = get_agent_notes("Buyer")
notes.save("budget_constraint", "$100 per item")
notes.save("preferred_colors", "blue, red, green")

notes.get("budget_constraint")  # Returns "$100 per item"
notes.get_all()  # Returns all saved state
```

Data is persisted to `logs/agent_notes/agent_notes.json` and shared across all agents.

### `utils.py` - Prompt Building

#### `build_system_prompt(agent_names, requirements_file="input.txt")`

Reads user-provided requirements from a file and constructs a comprehensive system prompt:

```python
from lib.utils import build_system_prompt

# Single agent
system_prompt = build_system_prompt("Buyer")

# Multi-protocol
system_prompt = build_system_prompt(["Buyer", "Merchant"])
```

**System Prompt Structure**:
1. **Agent Introduction**: "You are a {agent} agent."
2. **User Requirements**: Content from `input.txt`
3. **BSPL Explanation**: Multi-agent protocol concepts
4. **Protocol-Aware Guidance**: Role-specific message types (extracted from BSPL)
5. **Option Selection Strategy**: How to interpret bound parameters and choose messages
6. **Tool & Format Guidance**: Parameter rules, response format, tool usage

**Example System Prompt Section**:
```
You are a Wrapper agent.

The user has communicated the requirements to be as follows: 
Wrap all items with bubblewrap if fragile, paper otherwise.

BSPL Protocol Explanation:
You are participating in BSPL (Blindingly Simple Protocol Language) protocol enactments...
Roles are named agents (e.g., Merchant, Buyer)
Messages are directed communication with parameters marked as `out` (sender provides) 
or `in` (requires prior binding from other messages)

PROTOCOL-SPECIFIC GUIDANCE FOR YOUR ROLE(S):
In Logistics protocol, your role (Wrapper) is responsible for:
  - SENDING these message types: Wrapped
  - You may need to send MULTIPLE different message types as the protocol progresses

CRITICAL: BOUND PARAMETERS ARE READY TO USE
- When you see a message option with [BOUND: orderID=xyz, ...], those parameters are ALREADY SET
- BOUND parameters ARE HELPFUL - they reduce the number of values you need to fill in
- Do NOT skip or avoid options just because they have BOUND parameters
```

#### `build_user_prompt(agent_name, social_state, options, ...)`

Constructs user prompt with:
- Current agent context
- Message history from social state (last 10 messages)
- Available options with bound parameters highlighted
- Parameter requirements (what must be filled)

**Example User Prompt**:
```
You are agent 'Wrapper'. Choose at most one option, or return null.

Message History:
=== MESSAGE HISTORY ===
1. RequestWrapping (from Merchant to Wrapper)
   orderID: 123
   item: plate
=== END HISTORY (1 messages) ===

Options:
0) Wrapped [BOUND: orderID=123, item=plate] - FILL ONLY: [wrapping]
```

### Dynamic Adapter Manager

Creates and manages adapters for any protocol/role combination. Enables multiple agents running simultaneously with coordinated decision-making:

```python
from lib.dynamic_adapter_manager import create_adapter_for_role

# Create adapters for multiple roles
adapters = {}
for protocol, role in [('Purchase', 'Buyer'), ('Logistics', 'Merchant')]:
    adapter, error = create_adapter_for_role(protocol, role, color_idx=0)
    if not error:
        adapters[f"{protocol}:{role}"] = adapter

# Each adapter gets a multi-protocol decision handler
for adapter_key, adapter_instance in adapters.items():
    handler = await _get_multi_protocol_decision_handler(adapter_key)
    adapter_instance.decision()(handler)

# Start all adapters concurrently
await asyncio.gather(*[a.start() for a in adapters.values()])
```

**Multi-Protocol Decision Making**:
- The LLM receives state from ALL active adapters
- When an adapter is triggered, the LLM decides which role should act
- Requests are analyzed against all protocol contexts
- Prevents conflicts and ensures cross-protocol coordination

## LLM Integration: Prompt Construction & Execution

### System Prompt Flow

1. **Initial Setup** (in `ahoy.py`):
   ```python
   from lib.utils import build_system_prompt
   system_prompt = build_system_prompt(agent_name)
   # Returns ~1500 tokens of protocol guidance + user requirements
   ```

2. **Cached on First Decision**:
   ```python
   # In llm_client.py, inside choose_and_bind()
   if _system_prompt_cache is None:
       _system_prompt_cache = build_system_prompt(adapter_name)
   ```

3. **Reused for Subsequent Calls**:
   - Same system prompt used for all decisions in a session
   - Reduces redundant LLM context and API costs
   - Reset via `reset_llm_tracker()` at session start

### User Prompt Flow

User prompts are **constructed fresh** for each decision cycle with:

```python
# In choose_and_bind()
user_prompt = build_user_prompt(
    agent_name,
    social_state,          # Current protocol state
    options,               # Available messages
    recent_event=event,
    decision_count=cycle_num
)
```

**Example: Multi-Message Scenario**

Social State:
```json
{
  "all_messages": [
    {"schema_name": "RequestLabel", "payload": {"orderID": "123", "address": "Warehouse1"}},
    {"schema_name": "RequestWrapping", "payload": {"orderID": "123", "item": "plate"}}
  ]
}
```

Available Options:
```
0) RequestLabel [BOUND: orderID=123, address=Warehouse1] - FILL ONLY: []
1) RequestWrapping [BOUND: orderID=123, item=plate] - FILL ONLY: [wrapping]
```

LLM Response (Option 1):
```json
{"choice": 1, "params": {"wrapping": "bubblewrap"}, "tool_requests": []}
```

### Parameter Handling

**Bound Parameters** (auto-provided by protocol):
- Extracted from prior message bindings
- Displayed in `[BOUND: key=value]` format
- **Must NOT be provided by LLM** (already set)

**Missing/Fill-Only Parameters**:
- Extracted from message schema
- Listed in `FILL ONLY: [param1, param2]`
- **Must be provided by LLM**

**Auto-Generated IDs**:
- Parameters marked as 'key' in BSPL schema
- Automatically generated as UUIDs if not bound
- No LLM input needed

```python
# In utils.py
def auto_generate_id_parameters(partial_message):
    """Generate UUIDs for unbound 'key' parameters."""
    generated_ids = {}
    for param_name in partial_message.schema.parameters:
        if is_key_param(param_name) and not already_bound(param_name):
            generated_ids[param_name] = str(uuid.uuid4())
    return generated_ids
```

## Example: Complete Decision Cycle

### 1. Initial State
Agent (Wrapper) has received `RequestWrapping` message.

### 2. System Prompt (Cached)
```
You are a Wrapper agent.
Requirements: Wrap fragile items with bubblewrap...
In Logistics protocol, your role (Wrapper) is responsible for SENDING: Wrapped
CRITICAL: BOUND PARAMETERS ARE READY TO USE...
```

### 3. User Prompt (Fresh)
```
You are agent 'Wrapper'. Choose at most one option, or return null.

Message History:
1. RequestWrapping (from Merchant to Wrapper)
   orderID: abc123
   item: glass

Options:
0) Wrapped [BOUND: orderID=abc123, item=glass] - FILL ONLY: [wrapping]
```

### 4. LLM Response
```json
{"choice": 0, "params": {"wrapping": "bubblewrap"}, "tool_requests": []}
```

### 5. Parameter Binding & Execution
- Validate choice index: ✓ (0 < 1)
- Extract filled params: `{"wrapping": "bubblewrap"}`
- Get bound params: `{"orderID": "abc123", "item": "glass"}`
- Merge & create message:
  ```python
  message = Wrapped(
      wrapping="bubblewrap",
      orderID="abc123",
      item="glass"
  )
  ```
- Send via adapter: `await adapter.send(message)`

### 6. Protocol State Update
Adapter's history is updated with new message, becoming available context for next decision.

## Configuration & Protocol Access

Access protocol metadata without hardcoding names:

```python
from configuration import systems

# Get all systems
for system_name, system_data in systems.items():
    protocol = system_data["protocol"]
    roles = system_data["roles"]
    print(f"{system_name}: {list(roles.keys())}")
    # Output:
    # Purchase: [Buyer, Seller, Shipper]
    # Logistics: [Merchant, Wrapper, Labeler, Packer]

# Get specific protocol
purchase = systems["Purchase"]["protocol"]
buyer_role = purchase.roles["Buyer"]
```

## Logging & Debugging

### File Structure
```
logs/
├── agents.log              # All agent output (start.ps1 aggregation)
├── generic_agent_debug_*.log  # Detailed LLM decision logs
├── wrapper.log, merchant.log  # Per-agent logs
└── agent_notes/
    └── agent_notes.json    # Shared agent memory
```

### Debug Logging
Enable debug output in agents:

```python
from lib.ui_manager import setup_logging

debug_logger, console_logger = setup_logging("logs/agent.log", mode='a')

def log_debug(msg):
    debug_logger.debug(msg)

log_debug(f"Current state: {adapter.history}")
```

### LLM Call Tracking
Monitor LLM usage across session:

```python
from lib.llm_client import get_llm_tracker

tracker = get_llm_tracker()
if tracker:
    print(f"LLM Calls: {tracker.call_count}/{tracker.max_calls}")
    print(f"Elapsed: {tracker.get_elapsed_seconds():.1f}s / {tracker.max_duration_seconds}s")
```

## Testing

### Test Categories

| Module | Purpose | Coverage |
|--------|---------|----------|
| `test_configuration.py` | Protocol loading and system init | Protocol specs, role mapping |
| `test_state_manager.py` | BSPL state serialization | Message history, binding extraction |
| `test_agent_notes.py` | Persistent agent memory | Save/load key-value pairs |
| `test_protocol_discovery.py` | Protocol introspection | Role/message extraction |
| `test_llm_client.py` | LLM client behavior (mocked) | Prompt construction, response parsing |
| `test_utils.py` | Utility functions | Prompt building, ID generation |

### Running Tests
```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_configuration.py -v

# With coverage report
pytest tests/ --cov=lib --cov-report=term-missing

# Match pattern
pytest tests/ -k "protocol" -v
```

### Example Test
```python
def test_system_prompt_includes_agent_name():
    """System prompt should mention the agent's role."""
    prompt = build_system_prompt("Buyer")
    assert "Buyer" in prompt
    assert "requirements" in prompt.lower()

def test_user_prompt_shows_options():
    """User prompt should list available options with bound params."""
    options = [
        {"index": 0, "schema_name": "RequestToBuy", "missing_params": ["item"]}
    ]
    social_state = {"all_messages": []}
    prompt = build_user_prompt("Buyer", social_state, options)
    assert "RequestToBuy" in prompt
    assert "FILL ONLY" in prompt
```

## Common Patterns & Conventions

### Async/Await
All agent code uses Python `asyncio`:
```python
async def handle_message(msg):
    await adapter.send(response_msg)  # Always await sends
```

### Message Payload Access
Extract message data as dict:
```python
@adapter.reaction(RequestToBuy)
async def process(msg):
    item = msg["item"]           # Dict-like access
    full_payload = msg.payload   # Full payload dict
```

### Validation
Always validate protocol and role:
```python
from lib.protocol_discovery import validate_protocol_and_role

validate_protocol_and_role("Purchase", "Buyer")
# Raises ValueError if invalid
```

### Stop Signal Coordination
Agents coordinate startup/shutdown via temp files:
```python
STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

# In agent startup
try:
    adapter.start(shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH)))
except SystemExit:
    print("✅ Graceful shutdown")
```

## Adding New Protocols

1. Create BSPL specification: `protocols/{name}.bspl`
2. Add description: `protocols/protocol_descriptions.txt`
   ```
   YourProtocol: Brief description of the protocol purpose
   ```
3. Update `configuration.py`:
   ```python
   from bspl import load_file
   
   your_spec = load_file("protocols/yourprotocol.bspl")
   your_protocol = your_spec.protocols.get("YourProtocol")
   your_spec.export("YourProtocol")
   from YourProtocol import Role1, Role2, ...
   
   systems["YourProtocol"] = {
       "roles": {your_protocol.roles["Role1"]: Role1, ...},
       "protocol": your_protocol
   }
   ```
4. Create agent implementations (or reuse `ahoy.py`)

## Project Conventions

- **Timestamps**: `YYYYMMDD_HHMMSS` format in filenames
- **Max Tokens**: LLM calls default to 200 (user prompts), 1000 (completions)
- **Port Allocation**: Each role gets a unique port (8001-8010)
- **Temp Files**: Always use `Path(tempfile.gettempdir())` for cross-platform paths
- **Logging**: Use `setup_logging()` from `lib.ui_manager` for consistency

## Protocol Completion Detection

The system uses **LLM-based protocol analysis** to determine when a role has completed:

1. **Startup Analysis** (`ahoy.py`):
   ```python
   def _initialize_protocol_analysis(protocol_name, role_name):
       rule = extract_completion_rule_from_protocol(protocol_name, role_name)
       # Returns: (message_type, direction, count)
   ```

2. **LLM Analysis** (`protocol_completion_detector.py`):
   - Reads the BSPL protocol specification file
   - Reads user requirements from `input.txt`
   - Asks LLM: "What message type and count indicates completion for this role?"
   - Returns tuple: `(message_type, direction, count)`
     - `message_type`: e.g., "Packed", "Labeled" 
     - `direction`: "send" (role sends) or "receive" (role receives)
     - `count`: How many messages indicate completion

3. **Runtime Completion Check** (`ahoy.py`):
   ```python
   def _check_for_received_completion_message(adapter_ref):
       # Extracts all messages from adapter state
       # Counts messages matching the rule
       # Returns True if count reached
   ```

**Fallback**: Manual rules in `COMPLETION_RULES` dict are used if LLM extraction fails.

## Custom Event Handling (Optional Feature)

Agents can respond to **business logic events** (timeouts, alerts, thresholds) alongside protocol-driven reactions. This is completely optional and non-breaking for existing code.

### Overview

The framework includes `lib/custom_event_handler.py` which provides:

- **`CustomEventScheduler`**: Schedule events (inventory alerts, timeouts, thresholds)
- **`ConcurrentEventLock`**: Serialize access to LLM endpoint from both adapter and custom events
- **`EventDispatcher`**: Unified router for both event types
- **`CustomEventType`**: Enum for event categories (INVENTORY_ALERT, TIMEOUT_CHECK, THRESHOLD_BREACH, STALL_DETECTION, USER_DEFINED)

**Key Benefit**: Both adapter reactions (incoming messages) and custom events trigger the same LLM decision endpoint with proper locking.

### Integration with Existing Agents

**Minimal changes to `ahoy.py`** (< 30 lines):

1. Import custom event module:
```python
from lib.custom_event_handler import EventDispatcher, CustomEventScheduler
```

2. Create event dispatcher (optional):
```python
event_dispatcher = create_event_dispatcher_for_role("Purchase", "Buyer")
scheduler = event_dispatcher.scheduler
scheduler.schedule_inventory_alert(5.0, "Stock check", priority="high")
scheduler.schedule_timeout_check(15.0, "No progress timeout")
```

3. Dispatcher automatically integrates with adapter startup (no additional code needed in agent).

### Example: Adding Events to Existing Agent

```python
# In agents/buyer.py if __name__ == "__main__":
from agents.ahoy import create_event_dispatcher_for_role

# Create dispatcher before agent starts
dispatcher = create_event_dispatcher_for_role("Purchase", "Buyer")

# Schedule business logic events
scheduler = dispatcher.scheduler
scheduler.schedule_inventory_alert(5.0, "Low stock alert", priority="high")
scheduler.schedule_timeout_check(10.0, "Periodic protocol check")
scheduler.schedule_custom(20.0, "Market condition change",
                         metadata={"condition": "price_spike"})

# Agent runs normally - dispatcher handles events automatically
```

### Concurrent Event Safety

The `ConcurrentEventLock` ensures only one event source (adapter reaction OR custom event) accesses the LLM decision endpoint at a time:

```python
lock = ConcurrentEventLock(timeout=30.0)

# Adapter event
await lock.acquire("adapter")
# ... call LLM decision
lock.release("adapter")

# Custom event
await lock.acquire("custom_event")
# ... call LLM decision
lock.release("custom_event")

# Access lock history
history = lock.get_lock_history()
# Returns: [{"source": "adapter", "timestamp": "2025-02-03T10:15:30..."}, ...]
```

### Accessing Metrics

```python
metrics = dispatcher.get_metrics()
# Returns:
# {
#   "adapter_events": 5,
#   "custom_events": 3,
#   "total_decisions": 8,
#   "scheduler": {
#     "agent": "Buyer",
#     "protocol": "Purchase",
#     "role": "Buyer",
#     "scheduled_count": 3,
#     "fired_count": 3,
#     "events_by_type": {"timeout_check": 1, "inventory_alert": 2}
#   }
# }
```

### Backward Compatibility

- **No changes required** to existing agents if custom events not used
- **Opt-in feature**: Only agents that call `create_event_dispatcher_for_role()` enable it
- **Non-breaking**: All existing imports and code patterns work unchanged

## Ablation Study

The `ablation/` directory contains a comprehensive study isolating the value of two information sources in the AHOY system:

### Baselines

1. **Baseline 0 - Full AHOY** (`baseline0_full/`)
   - Full system with BSPL message comments and enabled set filtering
   - Reference implementation

2. **Baseline 1 - No Comments** (`baseline1_no_comments/`)
   - Same as Full AHOY, but BSPL comments stripped
   - Tests whether message comments improve decision quality

3. **Baseline 2 - No Filtering** (`baseline2_no_filtering/`)
   - LLM sees all possible messages (no enabled set filtering)
   - Uses exception-driven learning when invalid messages are chosen
   - Tests whether constraint filtering is necessary

### Measurement

Each baseline collects:
- **Accuracy**: % of valid (protocol-compliant) message choices
- **Exception Count**: Constraint violations (mainly for Baseline 2)
- **Transaction Success**: Completion of all required protocol steps
- **Latency**: Decision time per message
- **Recovery Pattern**: Correction after exceptions

### Running the Ablation Study

```bash
# Run all baselines on multiple protocols (3 runs each)
python ablation/run_ablation.py --protocols Purchase Logistics --runs 3

# Run specific baseline only
python ablation/run_ablation.py --baselines baseline1_no_comments --protocols Purchase --runs 1

# Analyze results
python ablation/analyze_results.py
```

Results are stored in `logs/ablation/` with per-baseline metrics and transaction logs.

## Known Limitations

- E2E tests not included (require real agent execution)
- LLM tests use mocks (no real API calls in test suite)
- Protocol state tests limited to serialization only

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ANTHROPIC_API_KEY not set` | `export ANTHROPIC_API_KEY="sk-ant-..."` |
| Port already in use | One agent already running that role; check `start.ps1` |
| Stop signal not created | Check file permissions in `%TEMP%` directory |
| No enabled messages | Role waiting for prior message; check message history |
| LLM threshold exceeded | Increase `max_calls`/`max_duration_seconds` in tracker init |

## References

- **BSPL Documentation**: https://gitlab.com/masr/bspl
- **Anthropic API**: https://docs.anthropic.com/en/api/
- **Protocol Files**: `protocols/*.bspl` (machine-readable specifications)
- **Demo Harness**: `demo/demo1/demo1_harness.py` (example execution)
