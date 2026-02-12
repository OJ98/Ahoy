# Demo Data Extractor

This tool extracts **decision-event sequences** from CHiPs-Ahoy execution logs for use in paper sections.

Rather than dumping raw message traces, it focuses on **LLM decision points**:
```
Event → Message History → Options → LLM Reasoning → Choice → Message Sent
```

## Usage

```bash
python extract_demo_data.py <log_file> [output_json]
```

### Example

```bash
python extract_demo_data.py ../../../logs/generic_agent_debug_20260210_000206.log demo3_extracted.json
```

## Output Structure

### `decision_events` (array)
Each event captures one LLM decision:

```json
{
  "decision_number": 3,
  "event_type": "Enabled Set Changed",
  "message_history": [
    {
      "number": 1,
      "type": "rfq",
      "sender": "Buyer",
      "receiver": "Seller",
      "parameters": {
        "ID": "ab534279-940b-...",
        "item": "glass vase"
      },
      "protocol": "Purchase"
    },
    {
      "number": 2,
      "type": "quote",
      "sender": "Seller",
      "receiver": "Buyer",
      "parameters": {
        "ID": "ab534279-940b-...",
        "item": "glass vase",
        "price": "42"
      },
      "protocol": "Purchase"
    }
  ],
  "available_options": [
    {
      "option_number": 0,
      "message_type": "Purchase/rfq",
      "missing_params": ["ID", "item"],
      "bound_params": {}
    },
    {
      "option_number": 3,
      "message_type": "Purchase/accept",
      "missing_params": ["address", "resp"],
      "bound_params": {
        "ID": "ab534279-...",
        "item": "glass vase",
        "price": "42"
      }
    }
  ],
  "llm_reasoning": "I need to analyze the current state...\n**Current Situation:**\n- Quote received for glass vase at $42...\n**Decision:**\nI should send an accept message...",
  "llm_choice": 3,
  "llm_choice_params": {
    "address": "123 Main Street, Portland, OR 97201",
    "resp": "Accepted - proceeding with purchase"
  },
  "message_sent": "accept"
}
```

**Fields:**
- `decision_number`: Sequential decision ID
- `event_type`: What triggered decision (InitEvent, Message Received, Enabled Set Changed)
- `message_history`: Messages visible to LLM at decision time (filtered, not all 187)
- `available_options`: All choices LLM could make from enabled set
- `llm_reasoning`: **Full text of LLM's RAW RESPONSE from logs** (shows reasoning AND choice JSON)
- `llm_choice`: Option number selected (0-indexed)
- `llm_choice_params`: Parameter values LLM bound
- `message_sent`: Type of message that was sent

**Use for:** Showing LLM understanding, demonstrating parameter binding, proving protocol awareness

### `metrics` (object)

```json
{
  "total_decision_events": 18,
  "protocols": ["Logistics", "Purchase"],
  "protocol_count": 2,
  "roles": [
    ["Logistics", "Merchant"],
    ["Logistics", "Labeler"],
    ["Purchase", "Buyer"],
    ["Purchase", "Seller"],
    ["Purchase", "Shipper"]
  ],
  "violations": 0,
  "exceptions": 0,
  "elapsed_time_seconds": 70,
  "completion_rules": {
    "Purchase:Buyer": "completed send x3",
    "Logistics:Merchant": "Packed receive x2"
  }
}
```

**Use for:** Proving zero errors, citing exact metrics, showing role-specific termination

### `parameter_isolation` (object)

Parameters grouped by protocol:

```json
{
  "Purchase:ID": {
    "parameter": "ID",
    "protocol": "Purchase",
    "values": [
      "0fcd009e-5823-425b-821a-6235a12ddfd6",
      "ab534279-940b-4382-90b1-a606692af9ad",
      "ebbadddb-83b7-4940-a456-221da1583ab9"
    ],
    "value_count": 3
  },
  "Logistics:orderID": {
    "parameter": "orderID",
    "protocol": "Logistics",
    "values": [
      "32dc1cf9-f8ca-4210-bee3-c6eef3f82100",
      "6aa820dd-8b40-426a-81f4-6546ca5607a1"
    ],
    "value_count": 2
  }
}
```

**Use for:** Proving parameter isolation (Purchase IDs ≠ Logistics orderIDs) — **KEY EVIDENCE FOR DEMO 3**

## How to Use For Paper Writing

### Demo 1 (Protocol Portability)
1. Extract: `python extract_demo_data.py log.json demo1.json`
2. Show decision_events 1-10 from Purchase protocol messages
3. Show decision_events 16-18 from Logistics protocol messages
4. Cite: "Same LLM logic, 0 exceptions, 0 violations across both"
5. Pull role-specific completion rules for evidence

### Demo 2 (Guarantee Validation)
- Use `parameter_isolation` to prove ID names don't collide
- Cite `violations: 0` (preconditions always met)
- Show `llm_reasoning` samples demonstrating LLM understood constraints

### Demo 3 (Concurrent Multiprotocol) — Primary Use Case
1. Extract multiprotocol run
2. Show message_history clean/deduplicated per decision
3. Pull `parameter_isolation` table for Purchase vs Logistics
4. Cite metrics: "0 violations, 0 exceptions, independent termination"
5. Extract decision_events 15-18 showing Logistics phase after Purchase
6. Show via `llm_reasoning` that LLM understood phase transitions

### Demo 4 (Flexible Protocols)
- Show decisions where multiple message morphs were available
- Extract `llm_reasoning` to prove LLM selected correct branch based on user intent
- Demonstrate parameter binding for chosen path

### Demo 5 (Custom Events)
- Show interleaved adapter + custom event decision points
- Prove both maintained consistent protocol state
- Pull reasoning showing unified event handling

## Example: Quick Python Analysis

```python
import json

with open('demo3_extracted.json') as f:
    data = json.load(f)

# Analyze decision 18 (last event)
last = data['decision_events'][-1]
print(f"Event: {last['event_type']}")
print(f"History: {len(last['message_history'])} msgs")
print(f"LLM chose: Option {last['llm_choice']} → {last['message_sent']}")

# Check parameter isolation
p_ids = data['parameter_isolation']['Purchase:ID']['values']
l_oids = data['parameter_isolation']['Logistics:orderID']['values']
print(f"\nPurchase IDs: {len(p_ids)} distinct values")
print(f"Logistics orderIDs: {len(l_oids)} distinct values")
print(f"Zero overlap: {len(set(p_ids) & set(l_oids)) == 0}")

# Show termination evidence
rules = data['metrics']['completion_rules']
print(f"\nTermination rules:")
for role, rule in rules.items():
    print(f"  {role}: {rule}")
```

## Advantages Over Raw Message Extraction

| Aspect | Raw Messages | Decision Events |
|--------|-------------|-----------------|
| Total entries | 187 messages | 18 events |
| Focus | Protocol state | LLM reasoning |
| LLM reasoning | Separate snippets | Integrated per event |
| Parameter tracking | All parameters | Only bound values |
| Event types | Not explicit | Clear event source |
| Message history | Always full | Filtered per decision |
| Paper readiness | Verbose | Compact, evidence-rich |

---

**Output Format:** All JSON, ready for loading into Python/LaTeX for evidence extraction and paper writing.
