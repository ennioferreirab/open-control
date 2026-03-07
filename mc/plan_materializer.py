"""Compatibility facade for :mod:`mc.contexts.planning.materializer`."""

import sys

from mc.contexts.planning import materializer as _impl

sys.modules[__name__] = _impl
