#!/usr/bin/env python3
"""
Baseline 1: No Message Comments

LLM sees the enabled set but WITHOUT inline comments from BSPL files.
This tests whether message comments aid comprehension.

Strategy:
- Patches the choose_and_bind function to use variant protocol definitions
- All other behavior identical to full AHOY
"""

import sys
from pathlib import Path

# Add parent directories to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set ablation mode environment variable
import os
os.environ["ABLATION_MODE"] = "baseline1_no_comments"

# Import the variant utilities BEFORE importing main ahoy
sys.path.insert(0, str(Path(__file__).parent))
from utils_variant import include_protocol_definitions_no_comments

# Patch lib.utils before importing ahoy
import lib.utils as utils_module
original_include_protocol_definitions = utils_module._include_protocol_definitions

def _include_protocol_definitions_patched():
    """Patched version that strips comments."""
    return include_protocol_definitions_no_comments()

utils_module._include_protocol_definitions = _include_protocol_definitions_patched

# Import and run the standard ahoy agent
# The patched _include_protocol_definitions will be used when prompts are built
from agents.ahoy import main, adapter, llm_client, ui

if __name__ == "__main__":
    try:
        # Run ahoy with patched protocol definitions (no comments)
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        ui.message("Baseline 1 (No Comments) interrupted by user")
    except SystemExit as e:
        # Let completion signals propagate
        raise
    except Exception as e:
        ui.error_occurred(str(e))
        raise
