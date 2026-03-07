"""Compatibility facade for :mod:`mc.contexts.execution.step_dispatcher`."""

import sys

from mc.contexts.execution import step_dispatcher as _impl

sys.modules[__name__] = _impl
