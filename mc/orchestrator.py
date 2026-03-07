"""Compatibility facade for :mod:`mc.runtime.orchestrator`."""

import sys

from mc.runtime import orchestrator as _impl

sys.modules[__name__] = _impl
