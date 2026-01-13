# CHiPs-Ahoy: Creating Human-in-the-loop Interaction Protocols

This repository contains the code for **CHiPs-Ahoy**, a multi-agent framework that demonstrates how LLM-driven agents can collaborate through formally-specified communication protocols to execute complex, real-world business transactions.

## Overview

CHiPs-Ahoy (Creating Human-in-the-loop Interaction Protocols, Ahoy!) is a research project exploring the intersection of:
- **Formal Protocol Specification** (BSPL)
- **Large Language Models** (Claude AI)
- **Protocol-Agnostic Multi-agent Systems** (Single LLM agent adapts to any protocol)
- **Human-in-the-loop Interaction** (User involvement in protocol execution)

The system demonstrates a **Generic LLM Agent** that can dynamically participate in multiple protocols based on user input. Currently supported:

1. **Purchase Protocol** - E-commerce transactions (Buyer, Seller, Shipper)
2. **Logistics Protocol** - Supply chain coordination (Merchant, Wrapper, Labeler, Packer)

The generic LLM agent automatically selects the appropriate protocol and role based on user input keywords, eliminating the need for role-specific agent implementations while maintaining decision autonomy and constraint satisfaction.

### Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Protocol Framework** | BSPL (Blindingly Simple Protocol Language) | Formal specification and enforcement of multi-agent communication rules |
| **AI/LLM** | Claude 3.5 Sonnet (Anthropic) | Intelligent agent decision-making with context awareness |
| **Concurrency** | Python asyncio | Parallel agent execution and non-blocking I/O |
| **Communication** | TCP/IP Sockets | Inter-agent message routing and synchronization |
| **State Management** | JSON Serialization | Protocol state tracking and agent context preservation |
| **Logging** | Timestamped Debug Logs | Comprehensive execution traces for analysis and debugging |

## Supported Protocols

### 1. Purchase Protocol

The **Purchase Protocol** demonstrates a realistic e-commerce transaction involving independent agents negotiating terms, executing payment, and coordinating delivery.

**Agents and Roles:**

- **Buyer:** Identify and acquire product within constraints
  - Decision Logic: Uses Claude AI to evaluate quotes against constraints
  - Behavior: Initiates RFQs, compares quotes, negotiates, verifies shipping
  - Constraints: Budget limits, delivery location, quality requirements

- **Seller:** Respond to quote requests and fulfill accepted orders
  - Decision Logic: Dynamic pricing and inventory management
  - Behavior: Quotes prices, confirms orders, coordinates with Shipper
  - State Tracking: Order history and fulfillment status

- **Shipper:** Manage logistics and delivery operations
  - Decision Logic: Shipping assignments and delivery confirmations
  - Behavior: Receives instructions from Seller, confirms delivery to Buyer
  - Constraints: Delivery address verification and status updates

**Protocol Definition:** `protocols/purchase.bspl`

### 2. Logistics Protocol

The **Logistics Protocol** demonstrates supply chain coordination for order fulfillment and package preparation.

**Agents and Roles:**

- **Merchant:** Initiates the logistics workflow
  - Behavior: Receives orders and coordinates with Wrapper for packaging
  - Decision Logic: Determines items to be wrapped and delivery requirements
  - Constraints: Order validation and inventory verification

- **Wrapper:** Prepares and wraps items
  - Behavior: Receives wrap instructions, packages items, passes to Labeler
  - Decision Logic: Determines wrapping method based on item type
  - State Tracking: Packaging status and item preparation logs

- **Labeler:** Adds address labels and tracking information
  - Behavior: Receives wrapped items, adds labels, passes to Packer
  - Decision Logic: Label format selection and tracking number generation
  - Constraints: Address validation and label completeness

- **Packer:** Final packaging and shipping preparation
  - Behavior: Receives labeled items, performs final packing checks
  - Decision Logic: Determines final box size and shipping method
  - Constraints: Weight limits and packaging standards

- **Coordinator** (optional): Orchestrates the supply chain workflow
  - Behavior: Monitors overall progress and handles exceptions
  - Decision Logic: Exception handling and workflow rerouting

**Protocol Definition:** `protocols/logistics.bspl`

### Message Flow and Protocol States

The purchase workflow follows this formal message sequence:

```
Phase 1: Quote Discovery
├─ Buyer → Seller:  rfq(ID, item)
│                   [Request for Quote]
│
└─ Seller → Buyer:  quote(ID, item, price)
                    [Price Quote Response]

Phase 2: Purchase Decision
├─ Buyer → Seller:  accept(ID, item, price, address, resp)
│                   [Accept offer and specify delivery address]
│
├─ Buyer → Seller:  reject(ID, item, price, outcome, resp)
│                   [Reject offer with reasoning]
│
└─ (Alternative: buyer waits for better quotes)

Phase 3: Fulfillment & Delivery
├─ Seller → Shipper: ship(ID, item, address)
│                    [Shipping instruction]
│
├─ Shipper → Buyer:  deliver(ID, item, address, outcome)
│                    [Delivery confirmation]
│
└─ Buyer → Seller:   completed(ID, item, price, satisfaction)
                     [Transaction completion & feedback]
```

### Protocol State Parameters

| Parameter | Type | Direction | Binding | Description |
|-----------|------|-----------|---------|-------------|
| **ID** | String | out | key | Unique transaction identifier (RFQ ID or Purchase ID) |
| **item** | String | out | derived | Product description (e.g., "pen") |
| **price** | Float | in | from quote | Negotiated purchase price in USD |
| **address** | String | out | - | Delivery address (Buyer specifies) |
| **outcome** | String | out | - | Transaction result reason (e.g., "Price acceptable", "Shipped successfully") |
| **resp** | String | out | - | Response message for acknowledgments |
| **satisfaction** | String | out | - | Buyer's satisfaction rating of completed transaction |
| **shipped** | Bool | in | from ship | Confirmation that item was shipped |

## System Architecture

### Multi-Agent Topology: Generic Agent + Protocol-Specific Agents

The system uses a **hybrid architecture** where a single generic LLM agent dynamically adapts to multiple protocols:

```
                    ┌──────────────────────────┐
                    │   User Input (input.txt)  │
                    │  "I need to buy a pen"   │
                    │   "Wrap 5 packages"      │
                    └────────────┬─────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│         Generic LLM Agent (agents/generic_llm_agent.py)          │
│                                                                   │
│  1. Reads user input and extracts requirements                  │
│  2. Uses keyword heuristics to infer protocol + role            │
│     - "buy", "purchase", "quote", "price" → Purchase:Buyer     │
│     - "wrap", "label", "pack", "coordinate" → Logistics:role  │
│  3. Dynamically creates BSPL adapter for detected protocol      │
│  4. Participates as LLM-driven agent in protocol conversation   │
│  5. Writes stop signal to temp directory when complete          │
└───────────────┬──────────────────────────────────────────────────┘
                │
                ├─ Claims role via temp file: maf_claimed_role_{PID}.txt
                │
                └─ Coordinates with hardcoded agents (never run duplicates)
                        │
        ┌───────────────┼───────────────┐
        ↓               ↓               ↓
   ┌─────────┐    ┌─────────┐    ┌──────────┐
   │ Seller  │    │Shipper  │    │Merchant, │
   │ Agent   │    │ Agent   │    │Wrapper,  │
   │ :8001   │    │ :8002   │    │Labeler,  │
   │(if role │    │(if role │    │Packer    │
   │not      │    │not      │    │(if roles │
   │claimed) │    │claimed) │    │not       │
   └─────────┘    └─────────┘    │claimed)  │
                                  └──────────┘
   (Purchase Protocol)            (Logistics Protocol)
   
   All agents communicate via TCP message queue
   Stop signal coordination: maf_stop_signal.txt in system temp directory
```

**Key Innovation: Protocol Detection**

The generic agent uses simple keyword heuristics to automatically determine which protocol to use:

```python
PURCHASE_KEYWORDS = {"buy", "purchase", "quote", "price", "seller", "shipping"}
LOGISTICS_KEYWORDS = {"wrap", "label", "pack", "coordinate", "parcel", "delivery"}

# Example: "I need to buy a pen" 
#  → Contains "buy" → Purchase protocol → Buyer role → Run generic_llm_agent
#  → Seller and Shipper agents also start (not claimed by generic agent)

# Example: "Wrap 5 packages for delivery"
#  → Contains "wrap" → Logistics protocol → Wrapper role → Run generic_llm_agent
#  → Other Logistics agents (Merchant, Packer, Labeler) start as needed
```

### Temp File Coordination System

To prevent port conflicts and coordinate agent startup, the system uses **PID-based temp files**:

**File Locations:**
- Windows: `%TEMP%\maf_claimed_role_{PID}.txt` (typically `C:\Users\{User}\AppData\Local\Temp`)
- Unix: `$TMPDIR/maf_claimed_role_{PID}.txt` (typically `/tmp`)

**Startup Sequence:**
1. `start.ps1`/`start.sh` launches `generic_llm_agent.py`
2. Generic agent writes its claimed role to `maf_claimed_role_{its_PID}.txt`
   - Content: `"Purchase:Buyer"` or `"Logistics:Wrapper"`
3. Start script reads claimed role file from temp directory
4. Script skips launching the hardcoded agent with that role (prevents port conflict)
5. Script launches other required agents for the protocol

**Shutdown Coordination:**
- When a transaction completes, the generic agent writes `maf_stop_signal.txt` to temp directory
- Start script monitors temp directory for this signal file
- When detected, all agent processes are gracefully terminated
- Signal file is automatically cleaned up

**Benefits:**
- Workspace stays clean (no temp files in project root)
- Works consistently across Windows/Linux/macOS
- PID-based naming prevents conflicts with simultaneous runs
- Relies on system-managed temp directory cleanup

### Multi-Protocol Support

The system now loads and manages multiple protocols simultaneously:

```
┌──────────────────────────────────────────┐
│     Available Protocols (BSPL files)      │
├──────────────────────────────────────────┤
│ 1. Purchase Protocol (protocols/purchase.bspl)
│    Roles: Buyer, Seller, Shipper         │
│    Focus: E-commerce transaction         │
│                                          │
│ 2. Logistics Protocol (protocols/logistics.bspl)
│    Roles: Merchant, Wrapper, Labeler,    │
│           Packer, Coordinator            │
│    Focus: Supply chain coordination      │
└──────────────────────────────────────────┘
```

Generic agent loads both protocols and selects based on user input keywords.

### Core Module Stack

```
┌─────────────────────────────────────────────┐
│  Generic Agent Initialization               │
│  (agents/generic_llm_agent.py)              │
│  • Read input.txt for user requirements     │
│  • Infer protocol from keywords             │
│  • Create dynamic BSPL adapter              │
│  • Determine LLM role in selected protocol  │
└─────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│  Protocol-Agnostic LLM Decision Making      │
│  • LLM-driven choice of enabled messages    │
│  • Constraint enforcement                  │
│  • Decision reasoning and audit logging     │
│  • Works for any BSPL protocol              │
└─────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│     LLM Integration (lib/llm_client.py)     │
│  • AnthropicLLMClient: Production Claude   │
│  • MockLLMClient: Testing/development      │
│  • Call tracking, timeout management       │
│  • Response parsing and validation         │
└─────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│  Protocol State Management & BSPL Adapter   │
│  • configuration.py: Protocol loading       │
│  • lib/state_manager.py: State tracking     │
│  • Message validation & routing enforcement │
│  • Binding resolution (parameter inherit.)  │
└─────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│   UI and Logging (lib/ui_manager.py)        │
│  • Debug file output (JSON format)          │
│  • Console status updates with metrics      │
│  • Error reporting and summaries            │
└─────────────────────────────────────────────┘
```

### Component Descriptions

```
┌──────────────────────────────────────────────────────────┐
│                    Purchase Protocol                      │
│  Defined in BSPL (protocols/purchase.bspl)               │
└──────────────────────────────────────────────────────────┘
         ↓              ↓              ↓
    ┌─────────┐   ┌─────────┐   ┌──────────┐
    │  Buyer  │   │ Seller  │   │ Shipper  │
    │ Agent   │   │ Agent   │   │ Agent    │
    │ :8000   │   │ :8001   │   │ :8002    │
    └────┬────┘   └────┬────┘   └────┬─────┘
         │             │             │
         └─────────────┼─────────────┘
                       │
                 (TCP Message Queue)
```

**Network Configuration:**
- **Buyer Agent:** `127.0.0.1:8000`
- **Seller Agent:** `127.0.0.1:8001`
- **Shipper Agent:** `127.0.0.1:8002`

### Core Module Stack

```
┌─────────────────────────────────────────────────┐
│      Agent Decision Layer (agents/buyer.py)      │
│  • LLM-driven choice of enabled messages        │
│  • Constraint enforcement (budget, delivery)    │
│  • Decision reasoning and audit logging         │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│       LLM Integration (lib/llm_client.py)        │
│  • AnthropicLLMClient: Production Claude API    │
│  • MockLLMClient: Testing/development mode      │
│  • Call tracking, timeout management, retry     │
│  • Response parsing and validation              │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│   Protocol State Management & BSPL Adapter      │
│  • configuration.py: Protocol configuration     │
│  • lib/state_manager.py: State serialization    │
│  • Message validation & routing enforcement     │
│  • Binding resolution (parameter inheritance)   │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│    UI and Logging (lib/ui_manager.py, utils.py) │
│  • Debug file output (JSON-compatible format)   │
│  • Console status updates with metrics          │
│  • Error reporting and transaction summaries    │
└─────────────────────────────────────────────────┘
```

### Component Descriptions

### Component Descriptions

**1. Generic LLM Agent** (`agents/generic_llm_agent.py`)
- **Purpose:** Single protocol-agnostic agent that participates in any BSPL protocol
- **Startup Logic:**
  1. Reads `input.txt` to extract user requirements
  2. Analyzes keywords to infer protocol and desired role
  3. Loads appropriate BSPL protocol dynamically
  4. Creates BSPL adapter for the selected protocol + role
  5. Writes claimed role to temp file: `maf_claimed_role_{PID}.txt`
- **Decision Making:** Uses Claude LLM to decide which enabled messages to send
- **Shutdown:** Writes `maf_stop_signal.txt` to temp directory when transaction completes
- **Advantage:** Single implementation that works for all protocols (no code duplication)

**2. Protocol-Specific Hardcoded Agents** (`agents/seller.py`, `agents/buyer.py`, etc.)
- **Purpose:** Deterministic agents for other roles in the protocol
- **Lifecycle:** Start script automatically skips agent with role claimed by generic LLM agent
- **Behavior:** Rule-based interactions (can be extended to LLM-driven)
- **Coordination:** All agents read from same temp directory for role coordination

**3. Protocol Selection Heuristic**

Keywords used to automatically detect protocol:

**Purchase Protocol Triggers:**
```
"buy", "purchase", "quote", "price", "order", "seller",
"shipping", "deliver", "cost", "budget"
```

**Logistics Protocol Triggers:**
```
"wrap", "label", "pack", "coordinate", "parcel",
"bundle", "organize", "logistics"
```

The generic agent checks user input for these keywords and selects the appropriate protocol.

**4. BSPL Adapter** (`configuration.py`)
- Loads formal protocol specifications from `protocols/*.bspl` files
- Validates protocol rules and message schemas
- Manages state bindings and parameter inheritance
- Enforces enabled message constraints per BSPL semantics
- Handles both Purchase and Logistics protocols

**5. LLM Integration** (`lib/llm_client.py`)
- **AnthropicLLMClient:** Direct integration with Claude API
  - Configurable model selection
  - Automatic timeout handling (30-second default)
  - Streaming response processing
  - Token limit awareness
- **MockLLMClient:** Deterministic testing mode
  - Returns fixed responses without API calls
  - Maintains identical interface to production client
- **LLMCallTracker:** Monitors usage metrics
  - Counts total calls across session
  - Tracks elapsed time since initialization
  - Enforces call and time thresholds

**6. State Management** (`lib/state_manager.py`)
- Extracts protocol state into JSON-serializable format
- Constructs social state: roles, bindings, message history
- Provides rich context for LLM decision-making
- Tracks message parameters for constraint checking

**7. UI/Logging** (`lib/ui_manager.py`)
- **Debug Logging:**
  - Timestamped file output in `logs/` directory
  - Complete LLM prompts and responses
  - Protocol state snapshots at each decision point
  - Enables full auditability and reproducibility
- **Status Updates:**
  - Minimal console output: message count + elapsed time
  - Non-intrusive feedback during execution

**8. Utilities** (`lib/utils.py`)
- Protocol requirements gathering from user input
- Message history construction for agent context
- User prompt generation with protocol documentation
- Graceful shutdown signal handling via temp directory

## Advanced Features

### LLM Call Tracking and Budget Management

The system automatically monitors LLM resource consumption with dual thresholds:

**Thresholds:**
- **Call Limit:** 20 consecutive API calls maximum
- **Time Limit:** 3 minutes (180 seconds) from initialization

**Mechanism:**
1. `LLMCallTracker` initialized at agent startup
2. Each LLM call increments counter and checks elapsed time
3. When either threshold is exceeded, the system gracefully terminates
4. User receives clear explanation of which limit was exceeded

**Benefits:**
- Prevents runaway costs from LLM API overages
- Ensures predictable execution timeframes
- Enables testing with cost control

### Constraint-Based Agent Decision Making

The Buyer agent demonstrates intelligent constraint satisfaction:

**Constraints:**
```
- Budget: $20 USD maximum (inclusive of all fees)
- Delivery: Must be to Raleigh, NC 27606
- Product: Functional pen with reasonable quality
- Transparency: All cost components documented before purchase
```

**Decision Logic:**
1. Receives multiple quote options from different sellers
2. Filters options against constraints (price ≤ $20)
3. Evaluates shipping costs and delivery timeframes
4. Selects option that maximizes value while respecting constraints
5. Documents decision reasoning in audit log

**Audit Trail:**
```json
{
  "decision": "accept",
  "option": "RFQ_A4BC9F8D_2133",
  "reason": "Selected lower-priced quote ($4 vs $5), maximizes remaining budget for shipping",
  "constraints_satisfied": true,
  "remaining_budget": 16.0
}
```

### Protocol Binding and Parameter Resolution

BSPL enforces a formal parameter binding model:

**Parameter Categories:**
- **out:** Sender generates the value
- **in:** Receiver must already know the value (from prior message)
- **key:** Identifies the transaction instance

**Example Resolution:**
```
Seller quotes: quote(ID='RFQ_123', item='pen', price=5)
              ↓
Buyer receives binding: ID='RFQ_123', item='pen', price=5
              ↓
Buyer can now send: accept(ID='RFQ_123', item='pen', price=5, address='...', resp='...')
                           └─────────────────────────────────────────┬──────────────┘
                                              Buyer provides these values
```

This ensures type-safe message sequencing and prevents protocol violations.

## Requirements and Dependencies

### System Requirements
- **Python:** 3.8 or higher
- **OS:** Windows, macOS, or Linux
- **Network:** Localhost network access (127.0.0.1)

### Python Dependencies

Install with:
```bash
pip install -r requirements.txt
```

**Core Dependencies:**
- `anthropic`: Claude API client for LLM integration
- `bspl` (research package): Protocol specification framework
- `python-dotenv`: Environment variable configuration

**Development Dependencies:**
- `pytest`: Testing framework
- `black`: Code formatting
- `mypy`: Type checking

### API Configuration

Set your Anthropic API key as an environment variable:

```bash
# Linux/macOS
export ANTHROPIC_API_KEY="your-key-here"

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "your-key-here"
```

Or create a `.env` file in the project root:
```
ANTHROPIC_API_KEY=your-key-here
```

## Experimental Design and Research Context

### Research Questions

CHiPs-Ahoy was designed to answer:

1. **Can formally-specified protocols enable structured multi-agent collaboration?**
   - BSPL provides formal semantics for message sequencing
   - Agents must respect protocol constraints

2. **Can LLMs make intelligent decisions within formal protocol constraints?**
   - Claude makes decisions within BSPL-enforced message constraints
   - Reasoning capability enables complex constraint satisfaction

3. **How do we ensure transparency and auditability in multi-agent systems?**
   - Every decision logged with full reasoning
   - Protocol state captured at each step
   - Enables post-hoc analysis and verification

4. **Can human users remain meaningfully in control of multi-agent transactions?**
   - Users specify constraints at system startup
   - Constraints enforced at agent decision points
   - Agents cannot exceed budgets or ignore user requirements

### Experimental Variations

The framework supports multiple experimental configurations:

**1. Agent Autonomy Levels**
- **Full LLM:** Buyer makes all decisions via Claude AI
- **Constrained LLM:** Claude must respect hard constraints
- **Rule-based:** Deterministic agent behavior

**2. Protocol Strictness**
- **Strict BSPL:** All messages validated against protocol schema
- **Flexible:** Agents can send messages outside formal protocol

**3. Cost Control**
- **Unlimited:** No LLM call limits (costs may exceed budget)
- **Limited:** Hard caps on API calls and execution time

**4. Transparency Levels**
- **Full Logging:** Every LLM call logged with prompts/responses
- **Minimal Logging:** Only final decisions recorded

## Example Execution Trace

Here's what a complete transaction looks like:

```
[INITIALIZATION]
Buyer agent starting at 21:33:06
Loaded BSPL protocol with 3 roles: Buyer, Seller, Shipper
LLM initialized: claude-3-5-sonnet-20241022
Thresholds: 20 calls / 180 seconds

[USER INPUT]
Enter system requirements:
Budget: $20
Delivery: Raleigh, NC 27606
Product: pen

[QUOTE PHASE]
Status: 1 messages, 5s elapsed
→ Buyer sends RFQ_BUYER_001 (generic inquiry)

Status: 2 messages, 6s elapsed
← Seller quotes $5 for pen

Status: 3 messages, 7s elapsed
→ Buyer sends RFQ_A4BC9F8D_2133 (exploratory)

Status: 4 messages, 8s elapsed
← Seller quotes $4 for pen

[DECISION PHASE]
Status: 5 messages, 60s elapsed
→ Buyer evaluates both quotes against $20 budget
→ Buyer selects lower-priced quote ($4)
→ Buyer sends accept(RFQ_A4BC9F8D_2133, address='Raleigh, NC 27606')

[COMPLETION]
Status: 6 messages, 67s elapsed
← Seller confirms acceptance
← Shipper begins delivery logistics
→ Buyer confirms satisfaction

[TRANSACTION COMPLETED]
Total: 6 LLM-driven messages in 67 seconds
Final Cost: $4 item + shipping
Budget Remaining: ~$16
Delivery: Confirmed to Raleigh, NC 27606
```

## Troubleshooting

### Common Issues

**"Connection refused" error**
- Ensure all three agents are running in separate terminals
- Check that ports 8000, 8001, 8002 are not in use
- Try restarting all agents

**"API rate limit exceeded"**
- Wait a few minutes before retrying
- Reduce `max_calls` threshold to prevent rapid requests
- Use mock client for testing instead of production API

**"Protocol error: message not enabled"**
- The protocol rules don't allow this message in current state
- Check message history in debug logs
- Verify all required parameters are bound

**Agents hang or don't respond**
- Check debug logs for error messages
- Increase timeout in agent files if network is slow
- Verify agents are receiving messages (check network)

## References and Related Work

This project builds on:
- **BSPL (Blindingly Simple Protocol Language)** - Formal protocol specification framework
- **Claude AI (Anthropic)** - State-of-the-art large language model
- **Multi-Agent Systems Literature** - Agent coordination and collaboration patterns
- **Human-in-the-loop AI** - User oversight of autonomous agent decisions

For the full research paper, see: "Creating Human-in-the-loop Interaction Protocols, Ahoy!"

## Contributing

This is a research project. To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Implement changes with tests
4. Submit a pull request with description of changes

## License

See [LICENSE](LICENSE) file for details.

## Quick Start

### Setup and Configuration

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set API Key:**
   ```bash
   # Linux/macOS
   export ANTHROPIC_API_KEY="your-key-here"
   
   # Windows PowerShell
   $env:ANTHROPIC_API_KEY = "your-key-here"
   ```

3. **Prepare input file** (`input.txt`):
   
   For **Purchase Protocol**:
   ```
   I need to buy a pen for less than $20.
   Delivery location: Raleigh, NC 27606
   
   Use Request IDs of the form RFQ-2026-001, RFQ-2026-002...
   ```
   
   For **Logistics Protocol**:
   ```
   Wrap and label 3 packages for delivery.
   
   Use Request IDs of the form ORD-001, ORD-002...
   ```

### Running the System

**Option 1: PowerShell Script (Recommended)**
```powershell
./start.ps1
```

This will:
1. Start the generic LLM agent
2. Wait for it to determine the protocol and claim a role
3. Start hardcoded agents for the detected protocol (skipping the claimed role)
4. Monitor for the stop signal in the temp directory
5. Gracefully shut down all agents when the transaction completes

**Option 2: Manual Terminal Execution**

Terminal 1 - Generic LLM Agent:
```bash
python agents/generic_llm_agent.py
```

Terminal 2+ - Other agents (Seller, Shipper for Purchase; Wrapper, Labeler, etc. for Logistics):
```bash
python agents/seller.py
python agents/shipper.py
# etc.
```

### User Interaction

The system reads requirements from `input.txt`. Include:

1. **Clear protocol keywords:**
   - Purchase: "buy", "purchase", "quote", "price"
   - Logistics: "wrap", "label", "pack", "coordinate"

2. **Request IDs** (required format):
   - Purchase: `RFQ-2026-001`, `RFQ-2026-002` (for quote requests)
   - Logistics: `ORD-001`, `ORD-002` (for orders)

3. **Specific requirements:**
   - Budget constraints
   - Delivery locations
   - Item descriptions
   - Timeline constraints

The generic agent will automatically:
1. Parse the input file
2. Detect the protocol based on keywords
3. Infer the appropriate role to play
4. Participate in protocol conversations
5. Make intelligent decisions using Claude LLM
6. Signal completion and shutdown all agents

### Monitoring Execution

**Real-time Status:**
```
Status: 0 messages, 0s elapsed
Status: 1 messages, 5s elapsed
Status: 2 messages, 8s elapsed
...
Status: 6 messages, 67s elapsed
Stop signal detected - shutting down all agents gracefully...
```

**Debug Logs:**
Debug logs are written to `logs/` directory with full execution traces:
```bash
# View logs while running (Linux/macOS)
tail -f logs/agents.log

# Or check specific agent logs
cat logs/agent_notes/agent_notes.json | python -m json.tool
```

## Execution and Usage

### Advanced Configuration

**Protocol Definition:** Edit `protocols/*.bspl` files
- Modify message types, roles, or rules
- Add new protocols by creating new .bspl files

**Agent Endpoints:** Configure in `configuration.py`
```python
AGENTS = {
    "Buyer": ("127.0.0.1", 8000),
    "Seller": ("127.0.0.1", 8001),
    "Shipper": ("127.0.0.1", 8002),
    "Merchant": ("127.0.0.1", 8003),
    "Wrapper": ("127.0.0.1", 8004),
    "Labeler": ("127.0.0.1", 8005),
    "Packer": ("127.0.0.1", 8006),
}
```

**LLM Configuration:** Set in `agents/generic_llm_agent.py`
```python
llm_client = AnthropicLLMClient(model="claude-3-5-sonnet-20241022")
```

**Thresholds:** Configure in `lib/llm_client.py`
```python
initialize_llm_tracker(
    max_calls=20,           # Maximum LLM API calls
    max_time=3 * 60        # Maximum execution time (seconds)
)
```

### Understanding Protocol Selection

The generic agent selects protocols using this logic:

```python
# Example 1: User input contains "buy"
if any(keyword in input.lower() for keyword in PURCHASE_KEYWORDS):
    protocol = Purchase
    # Infer role from secondary context
    role = "Buyer"  # or Seller, Shipper
    
# Example 2: User input contains "wrap"
if any(keyword in input.lower() for keyword in LOGISTICS_KEYWORDS):
    protocol = Logistics
    # Infer role from secondary context
    role = "Wrapper"  # or Merchant, Labeler, Packer
```

This automatic protocol selection eliminates the need to manually specify which protocol to use.

## Project Structure

```
MAF/
├── agents/
│   ├── generic_llm_agent.py         # Protocol-agnostic LLM agent
│   ├── buyer.py                     # Buyer agent (Purchase protocol)
│   ├── seller.py                    # Seller agent (Purchase protocol)
│   ├── shipper.py                   # Shipper agent (Purchase protocol)
│   ├── merchant.py                  # Merchant agent (Logistics protocol)
│   ├── wrapper.py                   # Wrapper agent (Logistics protocol)
│   ├── labeler.py                   # Labeler agent (Logistics protocol)
│   └── packer.py                    # Packer agent (Logistics protocol)
│
├── configuration.py                 # Agent endpoints & protocol loading
│
├── protocols/
│   ├── purchase.bspl                # BSPL spec: Purchase protocol
│   └── logistics.bspl               # BSPL spec: Logistics protocol
│
├── lib/
│   ├── __init__.py
│   ├── agent_notes.py               # Agent decision logging
│   ├── llm_client.py                # Claude API & mock clients
│   ├── state_manager.py             # Protocol state serialization
│   ├── ui_manager.py                # Console & debug logging
│   └── utils.py                     # Shared utilities
│
├── logs/                            # Generated debug log files
│   ├── agents.log                   # Consolidated event log
│   ├── agent_notes/
│   │   └── agent_notes.json         # Decision audit trail
│   └── (individual agent logs)
│
├── debug_scripts/
│   └── test_agent_notes.py          # Testing utilities
│
├── input.txt                        # User input for protocol/role selection
├── input_orig.txt                   # Original input template
├── start.ps1                        # PowerShell launch script
├── start.sh                         # Bash launch script
│
├── requirements.txt                 # Python dependencies
├── environment.yml                  # Conda environment (Linux)
├── environment-osx.yml              # Conda environment (macOS)
│
├── LICENSE                          # License file
└── README.md                        # This file
```

## Key Design Principles

### 1. **Protocol-Agnostic Architecture**
- Single generic LLM agent that dynamically adapts to any BSPL protocol
- Agent automatically detects protocol from user input keywords
- No need for protocol-specific agent implementations
- Dramatically reduces code duplication and maintenance burden

### 2. **Automatic Protocol & Role Selection**
- User specifies requirements in natural language via `input.txt`
- System automatically detects protocol based on keywords
  - "buy", "purchase", "quote" → Purchase protocol
  - "wrap", "label", "pack" → Logistics protocol
- System automatically infers appropriate agent role to play
- No manual configuration needed for protocol selection

### 3. **Temp File Coordination**
- PID-based files in system temp directory for coordination
- Prevents port conflicts between simultaneous runs
- Keeps workspace clean (no temp files in project root)
- Works consistently across Windows/Linux/macOS
- Automatic cleanup by OS temp management

### 4. **Protocol-First Architecture**
- All agent communication follows formal BSPL specification
- Protocol rules are enforced by framework, not agent code
- Message validation happens automatically
- Supports multiple protocols loaded simultaneously

### 5. **LLM-Driven Decision Making**
- Agents use Claude AI to make intelligent decisions within constraints
- LLM context includes full protocol state and decision history
- Responses include reasoning for auditability
- Works for any protocol without protocol-specific training

### 6. **Constraint Satisfaction**
- Budget constraints enforced before purchase commitment
- Delivery requirements verified
- Protocol-specific constraints automatically enforced
- Transparent decision-making with constraint reasoning

### 7. **Complete Auditability**
- Every decision is logged with full reasoning
- LLM prompts and responses recorded
- Protocol state snapshots at each step
- Enables reproduction and debugging of agent behavior

### 8. **Resource Management**
- LLM call limits prevent runaway costs
- Time limits ensure predictable execution
- Graceful termination when thresholds exceeded
- Clear user communication of constraint violations

## Advanced Usage

### Adding a New Protocol

To add a new protocol and have the generic agent support it:

1. **Create BSPL Protocol File**
   ```
   protocols/my_protocol.bspl
   ```
   Define roles, messages, and binding rules

2. **Load Protocol in configuration.py**
   ```python
   my_protocol = import_protocol("protocols/my_protocol.bspl")
   ```

3. **Add Keywords to Generic Agent**
   ```python
   # In agents/generic_llm_agent.py
   MY_PROTOCOL_KEYWORDS = {"keyword1", "keyword2", ...}
   
   if any(kw in input_text.lower() for kw in MY_PROTOCOL_KEYWORDS):
       return my_protocol, inferred_role
   ```

4. **Add Hardcoded Agents (Optional)**
   - Create `agents/role.py` for non-LLM roles
   - Start script will automatically include them

5. **Test with Generic Agent**
   - No additional agent code needed for LLM-driven roles
   - Update `input.txt` with keywords from your protocol
   - Run `./start.ps1`

### Testing with Mock LLM

For development without API costs:

```python
from lib.llm_client import MockLLMClient, initialize_llm_tracker

llm_client = MockLLMClient()  # Instead of AnthropicLLMClient
initialize_llm_tracker(max_calls=50, max_time=60*10)
```

### Analyzing Decision Logs

The agent notes JSON file provides structured decision data:

```bash
# View decision audit trail (Windows)
Get-Content logs/agent_notes/agent_notes.json | python -m json.tool

# Or Linux/macOS
cat logs/agent_notes/agent_notes.json | python -m json.tool
```

### Understanding Protocol Detection in Action

Example 1 - Purchase Protocol Detection:
```
Input: "I need to buy a pen for less than $20."
Keywords found: "buy"
Protocol selected: Purchase
Role inferred: Buyer
Action: generic_llm_agent runs as Buyer, other agents (Seller, Shipper) start separately
```

Example 2 - Logistics Protocol Detection:
```
Input: "Wrap 5 packages and label them for delivery."
Keywords found: "wrap", "label"
Protocol selected: Logistics
Role inferred: Wrapper
Action: generic_llm_agent runs as Wrapper, other agents (Merchant, Packer, Labeler) start separately
```

### Request ID Format Requirements

When specifying requirements in `input.txt`, include request IDs in the correct format:

**Purchase Protocol:**
- Format: `RFQ-YYYY-###` (Request For Quote)
- Example: `RFQ-2026-001`, `RFQ-2026-002`
- Used for quote request tracking

**Logistics Protocol:**
- Format: `ORD-###` (Order)
- Example: `ORD-001`, `ORD-002`
- Used for shipment/order tracking

The agent will use these IDs to bind protocol parameters and maintain transaction identity.

