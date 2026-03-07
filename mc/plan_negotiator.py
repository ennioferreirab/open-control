"""Compatibility facade for :mod:`mc.contexts.planning.negotiation`."""

import sys

from mc.contexts.planning import negotiation as _impl

sys.modules[__name__] = _impl
