"""Compatibility facade for :mod:`mc.contexts.agents.sync`."""

import sys

from mc.contexts.agents import sync as _impl

sys.modules[__name__] = _impl
