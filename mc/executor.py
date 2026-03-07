"""Compatibility facade for :mod:`mc.contexts.execution.executor`."""

import sys

from mc.contexts.execution import executor as _impl

sys.modules[__name__] = _impl
