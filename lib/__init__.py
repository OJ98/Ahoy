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
    reset_optimization_caches,
    save_state_to_memory,
    declare_protocol_and_role,
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
    build_system_prompt,
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

from .protocol_discovery import (
    get_all_protocols,
    get_protocol_structure,
    get_protocol_summary_for_llm,
    validate_protocol_and_role,
    get_protocol_object,
    get_role_object,
)

from .protocol_completion_detector import (
    extract_completion_rule_from_protocol,
    extract_request_response_from_protocol,
)

from .dynamic_adapter_manager import (
    create_adapter_for_role,
    get_color_for_protocol_role,
)

__all__ = [
    # LLM client
    "LLMClient",
    "AnthropicLLMClient",
    "choose_and_bind",
    "call_llm_with_timeout",
    "parse_llm_json_reply",
    "reset_optimization_caches",
    "MODEL_ID",
    # Tool calling for UID generation and state management
    "generate_unique_id",
    "save_state_to_memory",
    "declare_protocol_and_role",
    "get_agent_memory",
    "reset_agent_notes_storage",
    # UI & logging
    "UserInterface",
    "setup_logging",
    "log_debug",
    "log_console",
    # Utilities
    "build_system_prompt",
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
    # Protocol discovery & management
    "get_all_protocols",
    "get_protocol_structure",
    "get_protocol_summary_for_llm",
    "validate_protocol_and_role",
    "get_protocol_object",
    "get_role_object",
    # Protocol completion detection
    "extract_completion_rule_from_protocol",
    "extract_request_response_from_protocol",
    # Dynamic adapter management
    "create_adapter_for_role",
    "get_color_for_protocol_role",
]
