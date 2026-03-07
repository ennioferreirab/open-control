"""Compatibility facade for :mod:`mc.contexts.conversation.intent`."""

import sys

from mc.contexts.conversation import intent as _impl

sys.modules[__name__] = _impl
