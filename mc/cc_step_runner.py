"""Compatibility facade for :mod:`mc.contexts.execution.cc_step_runner`."""

import sys

from mc.contexts.execution import cc_step_runner as _impl

sys.modules[__name__] = _impl
