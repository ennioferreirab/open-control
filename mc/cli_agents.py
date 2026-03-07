"""Compatibility facade for :mod:`mc.cli.agents`."""

import sys

from mc.cli import agents as _impl

sys.modules[__name__] = _impl
