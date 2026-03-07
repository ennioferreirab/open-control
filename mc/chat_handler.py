"""Compatibility facade for :mod:`mc.contexts.conversation.chat_handler`."""

import sys

from mc.contexts.conversation import chat_handler as _impl

sys.modules[__name__] = _impl
