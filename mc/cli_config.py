"""Compatibility facade for :mod:`mc.cli.config`."""

import sys

from mc.cli import config as _impl

sys.modules[__name__] = _impl
