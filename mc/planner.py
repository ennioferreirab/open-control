"""Compatibility facade for :mod:`mc.contexts.planning.planner`."""

import sys

from mc.contexts.planning import planner as _impl

sys.modules[__name__] = _impl
