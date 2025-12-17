"""
Minimal multi-agent framework support library.

This package contains core utilities for LLM interactions, logging,
and tool calling for the multi-agent protocol system.
"""

from .llm_client import (
    LLMClient,
    AnthropicLLMClient,
    choose_and_bind,
    call_llm_with_timeout,
    parse_llm_json_reply,
    build_system_prompt,
    generate_unique_id,
    save_state_to_memory,
    get_agent_memory,
    reset_agent_notes_storage,
    MODEL_ID,
)

from .ui_manager import (
    UserInterface,
    setup_logging,
    log_debug,
    log_console,
)

from .utils import (
    build_user_prompt,
    build_message_history_from_social_state,
    shutdown_watcher,
)

from .state_manager import (
    extract_social_state,
    save_social_state,
    load_social_state_from_file,
    load_social_state_from_json,
    social_state_to_json,
    deserialize_social_state,
)

__all__ = [
    # LLM client
    "LLMClient",
    "AnthropicLLMClient",
    "choose_and_bind",
    "call_llm_with_timeout",
    "parse_llm_json_reply",
    "build_system_prompt",
    "MODEL_ID",
    # Tool calling for UID generation and state management
    "generate_unique_id",
    "save_state_to_memory",
    "get_agent_memory",
    "reset_agent_notes_storage",
    # UI & logging
    "UserInterface",
    "setup_logging",
    "log_debug",
    "log_console",
    # Utilities
    "build_user_prompt",
    "build_message_history_from_social_state",
    "shutdown_watcher",
    # State management
    "extract_social_state",
    "save_social_state",
    "load_social_state_from_file",
    "load_social_state_from_json",
    "social_state_to_json",
    "deserialize_social_state",
]
