"""Compatibility facade for :mod:`mc.contexts.conversation.service`."""

import sys

from mc.contexts.conversation import service as _impl

sys.modules[__name__] = _impl
