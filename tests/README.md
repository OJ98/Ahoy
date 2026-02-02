# CHiPs-Ahoy Testing Infrastructure

Minimal module-level testing for core components.

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_configuration.py -v

# Run with coverage
pytest tests/ --cov=lib --cov=. --cov-report=term-missing

# Run only unit tests (no mocks needed)
pytest tests/test_configuration.py tests/test_protocol_discovery.py -v
```

## Test Modules

| Module | Purpose |
|--------|---------|
| `test_configuration.py` | Protocol loading and system initialization |
| `test_state_manager.py` | Adapter state serialization |
| `test_agent_notes.py` | Agent notes persistence (JSON storage) |
| `test_protocol_discovery.py` | Protocol structure extraction for LLM |
| `test_llm_client.py` | LLM client behavior (mocked) |
| `test_utils.py` | Utility validation functions |
| `conftest.py` | Shared fixtures and configuration |

## Requirements

- `pytest` - Add to `requirements.txt` if not already present
- Project dependencies (`anthropic`, `bspl`)

## Adding Tests

1. Create `test_module.py` in `tests/` directory
2. Use fixtures from `conftest.py` (or add new ones)
3. Follow naming convention: `test_*.py` files, `test_*()` functions
4. Use parametrization for multiple scenarios:

```python
@pytest.mark.parametrize("protocol", ["Purchase", "Logistics"])
def test_protocol_exists(protocol):
    assert protocol in systems
```

## Known Limitations

- E2E tests not included (require real agent execution)
- LLM tests use mocks (not real API calls in CI)
- Protocol state tests limited to serialization only
