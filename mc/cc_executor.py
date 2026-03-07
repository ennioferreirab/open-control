"""Compatibility facade for :mod:`mc.contexts.execution.cc_executor`."""

import sys

from mc.contexts.execution import cc_executor as _impl

sys.modules[__name__] = _impl
