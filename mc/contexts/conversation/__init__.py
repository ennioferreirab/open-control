"""Conversation context public API."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ChatHandler": (
        "mc.contexts.conversation.chat_handler",
        "ChatHandler",
    ),
    "ConversationIntent": (
        "mc.contexts.conversation.intent",
        "ConversationIntent",
    ),
    "ConversationIntentResolver": (
        "mc.contexts.conversation.intent",
        "ConversationIntentResolver",
    ),
    "ConversationService": (
        "mc.contexts.conversation.service",
        "ConversationService",
    ),
    "ResolveResult": ("mc.contexts.conversation.intent", "ResolveResult"),
    "build_thread_context": (
        "mc.contexts.conversation.service",
        "build_thread_context",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    return getattr(module, attr_name)
