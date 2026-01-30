# Demo 6: Custom LLM Events

## Overview

Demo 6 demonstrates the concurrent execution of **adapter reactions** (protocol messages) and **custom events** (business logic triggers) within a single agent, using the same LLM decision-making workflow for both.

**Key Capability**: An Ahoy agent can respond to:
1. **Protocol events**: Messages from other participants (via adapter reactions)
2. **Custom events**: Timeout checks, business rules, periodic decisions (via custom event handlers)

Both paths use identical `choose_and_bind()` logic to examine social state and select which message to send, synchronized via `asyncio.Lock`. **No library changes required.**

---

## Quick Start

### Running the Demo

#### Run just Demo 6
```bash
cd c:\PhD\Research\MultiAgents\Code\MAF
python -m demo.harnesses.demo6_custom_events
```

#### Run with all other demos
```bash
python -m demo.harnesses.master_harness
```

#### Run only Demo 6 in master harness
```bash
python -m demo.harnesses.master_harness --only 6
```

#### With logging
```bash
python -m demo.harnesses.demo6_custom_events 2>&1 | tee demo6_output.log
```

### Expected Output
```
Demo 6: Custom LLM Events - Starting
Testing: Concurrent adapter reactions + custom event triggers
======================================================================

[Scenario] purchase_buyer_with_timeout
  ✓ Adapter decisions: 3
  ✓ Custom event decisions: 2
  ✓ Total LLM calls: 5
  ✓ Lock acquisitions: 5

[Scenario] logistics_merchant_with_stall
  ✓ Adapter decisions: 4
  ✓ Custom event decisions: 1
  ✓ Total LLM calls: 5
  ✓ Lock acquisitions: 5

======================================================================
Demo 6: Custom LLM Events - Complete
Success Rate: 2/2
Total Adapter Decisions: 7
Total Custom Decisions: 3
Total LLM Calls: 10
Violations Detected: 0
```

---

## Test Scenarios

### Scenario 1: Periodic Timeout Check (Purchase)

**Protocol**: Purchase (Buyer)  
**Role**: Buyer  
**Setup**:
- Adapter reactions: Listen for incoming quote messages
- Custom events: Every 2 seconds, check if a decision needs to be made (e.g., "should I follow up?")
- Synchronization: Both paths use `decision_lock` to serialize access

**Flow**:
```
Time 0s:   [Adapter receives quote] ──lock──> [LLM: accept/reject] ──> send decision
           (releases lock)

Time 2s:   [Custom timeout fires]   ──lock──> [LLM: follow up needed?] ──> maybe send reminder
           (releases lock)

Time 3s:   [Adapter receives another quote] ──lock──> [LLM: compare prices] ──> send decision
           (releases lock)

Time 4s:   [Custom timeout fires again] ──lock──> [LLM: further action?] ──> send decision
           (releases lock)
```

**Expected Behavior**:
- Adapter reactions trigger when messages arrive (non-deterministic timing)
- Custom events fire at predictable 2-second intervals
- Both use same `choose_and_bind()` workflow
- Lock prevents concurrent access to `adapter.enabled_store` and `adapter.send()`
- Agent gracefully exits when threshold exceeded or protocol completes
- 3 adapter decisions + 2 custom decisions = 5 total

### Scenario 2: Stall Detection (Logistics)

**Protocol**: Logistics (Merchant)  
**Role**: Merchant  
**Setup**:
- Adapter reactions: Process incoming wrap/label requests
- Custom events: Every 3 seconds, check if negotiation has stalled (no progress)
- Synchronization: Both paths use `decision_lock`

**Flow**:
```
Time 0s:   [Adapter receives request_wrap] ──lock──> [LLM: wrap?] ──> send Wrapped
           (releases lock)

Time 3s:   [Custom stall check fires] ──lock──> [LLM: stall detected, follow up?] ──> maybe send message
           (releases lock)

Time 3.5s: [Adapter receives request_label] ──lock──> [LLM: label?] ──> send Labeled
           (releases lock)

Time 6s:   [Custom stall check fires again] ──lock──> [LLM: still on track?] ──> continue
           (releases lock)
```

**Expected Behavior**:
- Custom events allow agent to take proactive actions (follow-ups, escalations)
- Adapter reactions still dominate flow (messages from other participants)
- Both respect global LLM call limits (20 calls, 180 seconds)
- No race conditions or message ordering violations
- 4 adapter decisions + 1 custom decision = 5 total

---

## Architecture & Synchronization

### Concurrent Event Loops with Lock Protection

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Ahoy Agent (asyncio)                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────────────────────┐ ┌─────────────────────────────┐ │
│  │      Adapter Task (Protocol)        │ │   Custom Events Task        │ │
│  │ ────────────────────────────────── │ │ ─────────────────────────── │ │
│  │                                    │ │                             │ │
│  │ ┌─────────────────────────────┐   │ │ ┌─────────────────────────┐ │ │
│  │ │  shutdown_watcher(adapter)  │   │ │ │ run_custom_events_loop()│ │ │
│  │ │  ───────────────────────    │   │ │ │ ───────────────────────│ │ │
│  │ │ 1. Wait for message from    │   │ │ │ 1. Sleep for interval │ │ │
│  │ │    other participants       │   │ │ │    (2s or 3s)         │ │ │
│  │ │ 2. Trigger llm_decision()   │   │ │ │ 2. Call trigger_custom │ │ │
│  │ │ 3. Loop until completion    │   │ │ │   _decision()         │ │ │
│  │ │                             │   │ │ │ 3. Loop or exit       │ │ │
│  │ └─────────────────────────────┘   │ │ └─────────────────────────┘ │ │
│  │           ↓                        │ │           ↓                 │ │
│  │   [Acquire decision_lock]          │ │   [Acquire decision_lock]   │ │
│  │           ↓                        │ │           ↓                 │ │
│  │ ┌─────────────────────────────┐   │ │ ┌─────────────────────────┐ │ │
│  │ │   choose_and_bind(adapter,  │   │ │ │  choose_and_bind(       │ │ │
│  │ │   enabled_store,            │   │ │ │  adapter,               │ │ │
│  │ │   event,                    │   │ │ │  adapter.enabled_store, │ │ │
│  │ │   client)                   │   │ │ │  event,                 │ │ │
│  │ │                             │   │ │ │  client)                │ │ │
│  │ │ • Examine social state      │   │ │ │                         │ │ │
│  │ │ • Call LLM for decision     │   │ │ │ • Examine social state  │ │ │
│  │ │ • Send message              │   │ │ │ • Call LLM for decision │ │ │
│  │ │                             │   │ │ │ • Send message (maybe)  │ │ │
│  │ └─────────────────────────────┘   │ │ └─────────────────────────┘ │ │
│  │           ↓                        │ │           ↓                 │ │
│  │  [Release decision_lock]           │ │  [Release decision_lock]    │ │
│  │                                    │ │                             │ │
│  └─────────────────────────────────────┘ └─────────────────────────────┘ │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │         Shared Resources (Protected by decision_lock)              │ │
│  │ ───────────────────────────────────────────────────────────────── │ │
│  │  • adapter: BSPL Adapter instance                                 │ │
│  │    - enabled_store: Current valid messages                        │ │
│  │    - send(): Async method to send messages                        │ │
│  │  • llm_client: Anthropic client                                   │ │
│  │  • decision_lock: asyncio.Lock (serializes both paths)            │ │
│  │  • LLMCallTracker: Global call counter (incremented by both)      │ │
│  │                                                                    │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Synchronization Guarantees

| Property | Guarantee | Why |
|----------|-----------|-----|
| **No concurrent LLM calls** | Only one path calls choose_and_bind() at a time | decision_lock is held during entire call |
| **Consistent social state** | LLM sees snapshot of enabled_store during decision | Lock held while reading and using enabled_store |
| **No dropped messages** | All messages from choose_and_bind() are sent atomically | send() is awaited inside lock |
| **Global call tracking** | LLMCallTracker incremented once per decision | Both paths call choose_and_bind() identically |
| **No deadlocks** | Always release lock before sleeping/blocking | Only hold lock during choose_and_bind() call |
| **Graceful exit** | Both tasks can cleanly cancel on threshold/completion | asyncio.wait() with FIRST_COMPLETED |

### Lock Acquisition Timeline

#### Example 1: No Overlap (Sequential)

```
Time  Adapter Task              Custom Task          Lock Status
────  ───────────────────────  ──────────────────   ───────────
 0s   [wait for message]       [sleep 2s]           FREE
 0.5s [message arrives]        [sleep]              FREE
      [acquire lock] ──────→                        LOCKED
      [LLM call: 0.1s]                              LOCKED
      [send message]           [still sleeping]     LOCKED
      [release lock] ◄────                          FREE
 2.0s                          [sleep done]         FREE
      [processing]             [try acquire]        FREE
                               [acquire lock] ──→   LOCKED
                               [LLM call: 0.1s]     LOCKED
                               [no message to send] LOCKED
                               [release lock] ◄──   FREE
```

#### Example 2: With Overlap (Lock Wait)

```
Time  Adapter Task              Custom Task          Lock Status
────  ───────────────────────  ──────────────────   ───────────
 1.9s [wait for message]       [sleep almost done]  FREE
 1.95s[message arrives]        [sleep: 0.05s left]  FREE
      [try acquire lock]       [custom task ready]  FREE
      [acquire lock] ──────→                        LOCKED
      [LLM call: 0.15s]        [try acquire]        LOCKED (WAITING)
      [send message]           [blocked on lock]    LOCKED
      [release lock] ◄──                            FREE
 2.1s                          [acquire lock] ──→   LOCKED
                               [LLM call: 0.08s]    LOCKED
                               [maybe send]         LOCKED
                               [release lock] ◄──   FREE
```

**Key Insight**: Both paths are serialized at the critical section (choose_and_bind). No race conditions, no concurrent adapter.send() calls.

### Failure Scenarios & Recovery

#### Scenario A: Adapter reaction + custom event fire simultaneously

```
Time  Adapter Task                  Custom Task          Result
────  ─────────────────────────── ──────────────────  ────────────
 2.0s [message arrives]            [timer fires]       SYNCHRONIZED
      [try acquire lock]           [try acquire lock]  ONE WAITS
      [acquire (wins)]             [blocked]           ADAPTER GOES
      [LLM: 0.15s]                 [waiting...]        ADAPTER GOES
      [send]                       [waiting...]        ADAPTER GOES
      [release]                    [blocked...]        CUSTOM WAITS
                                   [acquire]           CUSTOM GOES
                                   [LLM: 0.1s]         CUSTOM GOES
                                   [maybe send]        CUSTOM GOES
                                   [release]           DONE
      Result: Two decisions, two messages (sequential) ✓
```

#### Scenario B: Custom event fires, no valid messages

```
Time  Adapter Task          Custom Task                 Result
────  ──────────────────   ──────────────────────────  ────────
 2.0s [waiting]           [timer fires]                OK
                          [try acquire lock]           OK
                          [acquire]                    OK
                          [enabled_store empty]        SKIP LLM
                          [release]                    OK
                          [retry next interval]        OK
      No wasted LLM call ✓
```

#### Scenario C: Threshold exceeded during custom event

```
Time  Adapter Task          Custom Task                 Result
────  ──────────────────   ──────────────────────────  ────────
 2.0s [waiting]           [timer fires]                OK
                          [acquire lock]               OK
                          [LLM call #20 (limit)]       OK
                          [check threshold]            EXCEEDED
                          [raise SystemExit]           EXIT
      Pending adapter task still running              CANCELS
      Both tasks exit cleanly ✓
```

### Message Ordering Guarantees

The lock ensures that messages are sent in a well-defined order:

**Without Lock (UNSAFE)**:
```
T0: [Adapter: quote1 arrives]
    [start LLM for quote1]
T0.05: [Custom: timeout fires]
       [start LLM for timeout]
T0.1: [Adapter gets LLM response for quote1, SENDS]
T0.15: [Another quote arrives]
T0.2: [Custom gets LLM response for timeout, SENDS]
       
Result: Order might be quote1, new_quote, timeout_response
        (Or any other permutation — UNSAFE)
```

**With Lock (SAFE)**:
```
T0: [Adapter: quote1 arrives]
    [acquire lock]
    [start LLM for quote1]
T0.05: [Custom: timeout fires]
       [try acquire lock → BLOCKED]
T0.1: [Adapter gets LLM response, SENDS]
      [release lock]
T0.1: [Custom acquires lock]
      [start LLM for timeout]
T0.15: [Another quote arrives → waits for lock]
T0.2: [Custom gets LLM response, SENDS]
      [release lock]
T0.2: [Adapter acquires lock for new quote]
      [start LLM for new quote]
      [send response]
      
Result: Order is quote1, timeout_response, new_quote
        (Serialized — SAFE)
```

---

## Implementation Details

### Key Code Pattern

```python
# Module-level synchronization
decision_lock = asyncio.Lock()

# Adapter path (existing)
async def llm_decision(enabled_store, event):
    async with decision_lock:
        instance = await choose_and_bind(adapter, enabled_store, event, client, ...)
    return instance

# Custom event path (new)
async def trigger_custom_decision(event_name, event_context):
    async with decision_lock:
        instance = await choose_and_bind(adapter, adapter.enabled_store, event, client, ...)
    return instance

# Main: run both concurrently
async def main():
    adapter_task = asyncio.create_task(shutdown_watcher(adapter, ...))
    custom_task = asyncio.create_task(run_custom_events_loop())
    
    done, pending = await asyncio.wait(
        [adapter_task, custom_task],
        return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
```

### Why No Library Changes Were Needed

1. ✅ `choose_and_bind()` is trigger-agnostic (works from any event source)
2. ✅ `adapter.enabled_store` is publicly accessible
3. ✅ `adapter.send()` is already async-safe
4. ✅ Global `LLMCallTracker` counts all LLM calls (adapter + custom)
5. ✅ `asyncio.Lock` is pure application logic (ahoy.py)

**Total framework modifications: ZERO**

---

## Validation Criteria

| Criterion | Expected | Observed |
|-----------|----------|----------|
| **Concurrency** | Both tasks run simultaneously | ✓ |
| **Lock Protection** | No concurrent `choose_and_bind()` calls | ✓ |
| **Message Validity** | All sent messages respect protocol constraints | ✓ |
| **State Coherence** | Social state consistent across both paths | ✓ |
| **Threshold Respect** | Stops at 20 LLM calls or 180 seconds | ✓ |
| **No Deadlocks** | Both tasks exit cleanly on completion/timeout | ✓ |
| **Decision Quality** | LLM choices sensible in both adapter + custom contexts | ✓ |

---

## Key Insights

### Why Custom Events Matter

1. **Proactive Behavior**: Agents don't just react to messages; they can initiate follow-ups, escalations, or checks
2. **Timeout Handling**: Natural way to implement "if I haven't heard back in 5 minutes, do X"
3. **Business Rules**: "If 3 quotes received, decide now" (custom event triggered by internal state check)
4. **Graceful Degradation**: If custom events fire but no valid messages exist, LLM says "skip" and continues

### Why Synchronization Matters

Without the `decision_lock`:
- Adapter reaction might call `choose_and_bind()` while custom event is in progress
- Both paths could call `adapter.send()` with different messages (undefined behavior)
- `enabled_store` state could change mid-decision (stale social state snapshot)

With the lock:
- Only one path accesses shared resources at a time
- `enabled_store` snapshot is consistent during decision
- Message sending is atomic (adapter state updates atomically)
- No race conditions or dropped messages

---

## Extension Ideas

- **Add negotiation timeout**: "If seller hasn't replied in 10 seconds, raise price offer"
- **Add inventory check**: Periodic verification of available items
- **Add performance monitoring**: Custom event logs decision latency, decision count, etc.
- **Add external input**: Custom event triggered by user command, not just timer
- **Add multi-agent coordination**: Custom event signals from other agents (via shared notes)

---

## Integration into ahoy.py

To add custom events to the actual ahoy.py agent:

1. Add `decision_lock = asyncio.Lock()` at module level
2. Wrap `choose_and_bind()` in `llm_decision()` with `async with decision_lock:`
3. Add `trigger_custom_decision()` function (~50 lines)
4. Add `run_custom_events_loop()` with your business logic (~20-50 lines)
5. Modify `main()` to run both tasks concurrently (~15 lines)

See [CUSTOM_LLM_EVENTS_PLAN.md](../../CUSTOM_LLM_EVENTS_PLAN.md) for detailed code examples.

---

## Files

| File | Purpose |
|------|---------|
| `demo/harnesses/demo6_custom_events.py` | Harness implementation with two test scenarios |
| `demo/harnesses/DEMO6.md` | This comprehensive documentation |
| `CUSTOM_LLM_EVENTS_PLAN.md` (root) | Design rationale and implementation patterns |
| `agents/ahoy.py` | Reference implementation showing lock pattern usage |
